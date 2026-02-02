from __future__ import annotations

from typing import Any
import json
import re

import httpx
from sqlalchemy import select, text
from sqlalchemy.engine import URL, create_engine
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Agent, AgentMessage, Connection, ApiRoute
from app.security import EncryptionError, decrypt_secret
from app.services.scan import ConnectionInfo
from app.services.rag import search_embeddings


def _openai_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }


def _format_connections(connections: list[Connection]) -> list[str]:
    return [f"{connection.name} ({connection.host}:{connection.port}/{connection.database})" for connection in connections]


def _format_routes(routes: list[ApiRoute]) -> list[str]:
    return [f"{route.method} {route.base_url}{route.path}" for route in routes]


SELECT_FORBIDDEN_RE = re.compile(
    r"\b(insert|update|delete|drop|alter|create|grant|revoke|truncate|call|execute|commit|rollback)\b",
    re.IGNORECASE,
)


def _sanitize_query(query: str) -> str | None:
    if not query:
        return None
    cleaned = query.strip()
    if ";" in cleaned[:-1]:
        return None
    if cleaned.endswith(";"):
        cleaned = cleaned[:-1].strip()
    lowered = cleaned.lower()
    if not (lowered.startswith("select") or lowered.startswith("with")):
        return None
    if SELECT_FORBIDDEN_RE.search(lowered):
        return None
    return cleaned


def _build_client_engine(info: ConnectionInfo):
    url = URL.create(
        "postgresql+psycopg2",
        username=info.username,
        password=info.password,
        host=info.host,
        port=info.port,
        database=info.database,
        query={"sslmode": info.ssl_mode},
    )
    return create_engine(url, pool_pre_ping=True)


def _build_system_prompt(
    agent: Agent,
    connections: list[Connection],
    routes: list[ApiRoute],
    context: list[dict[str, Any]],
) -> str:
    lines = [
        f"Você é o agente '{agent.name}'.",
        f"Função principal: {agent.role or 'não definida'}.",
        f"Template: {agent.template or 'não definido'}.",
        f"Modelo configurado: {agent.model}.",
        f"Permissões: bancos externos={'sim' if agent.allow_db else 'não'}, APIs={'sim' if agent.allow_apis else 'não'}.",
        "As conexões externas abaixo são separadas do banco padrão do aplicativo que guarda o catálogo.",
        f"Conexões externas cadastradas: {_format_connections(connections) or ['nenhuma']}.",
        f"APIs cadastradas: {_format_routes(routes) or ['nenhuma']}.",
        f"Prompt base: {agent.base_prompt}",
        "Se precisar de dados, você pode solicitar execução de SELECTs antes de responder.",
        "Responda sempre em JSON válido com as chaves:",
        "- action: 'final' ou 'select'",
        "- content: resposta final quando action='final'",
        "- selects: lista de objetos quando action='select', cada item com:",
        "  - query: SQL SELECT (ou WITH ... SELECT), sem instruções de escrita.",
        "  - connection_id: opcional se houver mais de uma conexão disponível.",
    ]
    if agent.rag_prompt:
        lines.append(f"Prompt RAG: {agent.rag_prompt}")
    if agent.enable_rag:
        if context:
            lines.append(f"Contexto RAG: {context}")
        else:
            lines.append("Contexto RAG: nenhum contexto relevante encontrado.")
    return "\n".join(lines)


def _connection_info_from_model(connection: Connection) -> ConnectionInfo:
    try:
        password = decrypt_secret(connection.password_encrypted)
    except EncryptionError as exc:
        raise RuntimeError("Falha ao descriptografar a senha da conexão.") from exc
    return ConnectionInfo(
        host=connection.host,
        port=connection.port,
        database=connection.database,
        username=connection.username,
        password=password,
        ssl_mode=connection.ssl_mode,
    )


def _execute_selects(
    connection: Connection,
    selects: list[str],
    row_limit: int,
) -> list[dict[str, Any]]:
    info = _connection_info_from_model(connection)
    engine = _build_client_engine(info)
    results: list[dict[str, Any]] = []
    for query in selects:
        cleaned = _sanitize_query(query)
        if not cleaned:
            results.append(
                {
                    "connection_id": connection.id,
                    "query": query,
                    "error": "Query não permitida. Use apenas SELECT/CTE sem comandos de escrita.",
                    "columns": [],
                    "rows": [],
                    "row_count": 0,
                }
            )
            continue
        wrapped = f"SELECT * FROM ({cleaned}) AS atlasrag_select LIMIT :limit"
        try:
            with engine.connect() as conn:
                result = conn.execute(text(wrapped), {"limit": row_limit})
                rows = [dict(row) for row in result.mappings().all()]
                results.append(
                    {
                        "connection_id": connection.id,
                        "query": cleaned,
                        "columns": list(result.keys()),
                        "rows": rows,
                        "row_count": len(rows),
                    }
                )
        except Exception as exc:
            results.append(
                {
                    "connection_id": connection.id,
                    "query": cleaned,
                    "error": str(exc),
                    "columns": [],
                    "rows": [],
                    "row_count": 0,
                }
            )
    return results


def _compact_result_payload(payload: list[dict[str, Any]], limit: int = 4000) -> str:
    raw = json.dumps(payload, ensure_ascii=False, default=str)
    if len(raw) <= limit:
        return raw
    return raw[:limit] + "..."


def _parse_agent_action(content: str) -> dict[str, Any] | None:
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return data


def build_agent_reply(
    db: Session, agent: Agent, user_message: str
) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]], str | None]:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required")

    connections: list[Connection] = []
    routes: list[ApiRoute] = []
    if agent.connection_ids:
        connections = db.scalars(select(Connection).where(Connection.id.in_(agent.connection_ids))).all()
    if agent.api_route_ids:
        routes = db.scalars(select(ApiRoute).where(ApiRoute.id.in_(agent.api_route_ids))).all()

    citations: list[dict[str, Any]] = []
    context: list[dict[str, Any]] = []
    if agent.enable_rag:
        matches = search_embeddings(
            db,
            user_message.strip(),
            settings.rag_top_k,
            scope={"connection_ids": agent.connection_ids, "api_route_ids": agent.api_route_ids},
        )
        filtered_matches = []
        for match in matches:
            if not agent.allow_db and match.item_type in {"table", "column"}:
                continue
            if not agent.allow_apis and match.item_type == "api_route":
                continue
            filtered_matches.append(match)
        context = [match.meta for match in filtered_matches]
        citations = [{"item_type": match.item_type, "item_id": match.item_id} for match in filtered_matches]

    system_prompt = _build_system_prompt(agent, connections, routes, context)
    history = (
        db.query(AgentMessage)
        .filter(AgentMessage.agent_id == agent.id)
        .order_by(AgentMessage.id.desc())
        .limit(settings.agent_history_limit)
        .all()
    )
    history_messages = []
    for msg in reversed(history):
        if msg.role not in {"user", "assistant", "tool"}:
            continue
        if msg.role == "tool":
            history_messages.append({"role": "assistant", "content": f"RESULTADO_SELECT: {msg.content}"})
        else:
            history_messages.append({"role": msg.role, "content": msg.content})
    messages = [{"role": "system", "content": system_prompt}, *history_messages, {"role": "user", "content": user_message}]

    executed_selects: list[dict[str, Any]] = []
    tool_payload: str | None = None
    for _ in range(settings.agent_select_rounds):
        payload = {
            "model": agent.model,
            "messages": messages,
            "temperature": 0.2,
        }
        with httpx.Client(timeout=60) as client:
            response = client.post(
                "https://api.openai.com/v1/chat/completions",
                headers=_openai_headers(),
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        reply_content = data["choices"][0]["message"]["content"]
        action = _parse_agent_action(reply_content)
        if not action or action.get("action") == "final":
            answer = action.get("content") if action and action.get("content") else reply_content
            return answer, citations, executed_selects, tool_payload

        if action.get("action") != "select":
            return reply_content, citations, executed_selects, tool_payload

        if not agent.allow_db:
            return "O agente não tem permissão para executar consultas no banco.", citations, executed_selects, tool_payload
        if not connections:
            return "Nenhuma conexão disponível para executar selects.", citations, executed_selects, tool_payload

        requested = action.get("selects") or []
        if not isinstance(requested, list) or not requested:
            return reply_content, citations, executed_selects, tool_payload

        selects_by_connection: dict[int, list[str]] = {}
        default_connection_id = connections[0].id if connections else None
        for item in requested:
            if not isinstance(item, dict):
                continue
            query = item.get("query")
            if not query:
                continue
            connection_id = item.get("connection_id") or default_connection_id
            if not connection_id:
                continue
            selects_by_connection.setdefault(int(connection_id), []).append(str(query))

        if not selects_by_connection:
            return reply_content, citations, executed_selects, tool_payload

        for connection in connections:
            if connection.id not in selects_by_connection:
                continue
            results = _execute_selects(
                connection,
                selects_by_connection[connection.id],
                settings.agent_select_rows,
            )
            executed_selects.extend(results)

        tool_payload = _compact_result_payload(executed_selects)
        messages.append({"role": "assistant", "content": f"RESULTADO_SELECT: {tool_payload}"})

    return (
        "Contexto insuficiente após múltiplos selects. Vou responder com o que tenho.",
        citations,
        executed_selects,
        tool_payload,
    )
