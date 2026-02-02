"""Serviços de agentes: geração de respostas e contexto."""
from __future__ import annotations

from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.domain.models import Agent, AgentMessage, Connection, ApiRoute
from app.application.services.rag import search_embeddings
from app.application.services.sql_orchestrator import orchestrate_sql_rag


def _format_connections(connections: list[Connection]) -> list[str]:
    """Serializa conexões em formato amigável para prompt."""
    return [f"{connection.name} ({connection.host}:{connection.port}/{connection.database})" for connection in connections]


def _format_routes(routes: list[ApiRoute]) -> list[str]:
    """Serializa rotas de API em formato amigável para prompt."""
    return [f"{route.method} {route.base_url}{route.path}" for route in routes]


def _openai_headers() -> dict[str, str]:
    """Headers padrão para chamada OpenAI."""
    return {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }


def _call_llm(model: str, messages: list[dict[str, str]]) -> str:
    """Chama o modelo diretamente quando não há orquestração SQL."""
    payload = {"model": model, "messages": messages, "temperature": 0.2}
    with httpx.Client(timeout=60) as client:
        response = client.post(
            "https://api.openai.com/v1/chat/completions",
            headers=_openai_headers(),
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
    return data["choices"][0]["message"]["content"]


def _build_system_prompt(
    agent: Agent,
    connections: list[Connection],
    routes: list[ApiRoute],
    context: list[dict[str, Any]],
) -> str:
    """Constrói prompt do sistema com contexto do agente."""
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
        "Use o orquestrador SQL-RAG para decisões e respostas quando precisar consultar dados.",
    ]
    if agent.rag_prompt:
        lines.append(f"Prompt RAG: {agent.rag_prompt}")
    if agent.enable_rag:
        if context:
            lines.append(f"Contexto RAG: {context}")
        else:
            lines.append("Contexto RAG: nenhum contexto relevante encontrado.")
    return "\n".join(lines)


def build_agent_reply(
    db: Session, agent: Agent, user_message: str, user_message_id: int | None = None
) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]], str | None]:
    """Gera a resposta do agente com base em permissões e contexto."""
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required")

    if agent.allow_db and not agent.connection_ids:
        return (
            "Este agente não tem conexões selecionadas. Selecione uma conexão no cadastro do agente.",
            [],
            [],
            None,
        )

    # Busca conexões e rotas associadas ao agente.
    connections: list[Connection] = []
    routes: list[ApiRoute] = []
    if agent.connection_ids:
        connections = db.scalars(select(Connection).where(Connection.id.in_(agent.connection_ids))).all()
    if agent.api_route_ids:
        routes = db.scalars(select(ApiRoute).where(ApiRoute.id.in_(agent.api_route_ids))).all()

    # Contexto RAG apenas quando permitido.
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
    history_query = db.query(AgentMessage).filter(AgentMessage.agent_id == agent.id)
    if user_message_id is not None:
        history_query = history_query.filter(AgentMessage.id != user_message_id)
    history = (
        history_query.order_by(AgentMessage.id.desc())
        .limit(settings.agent_history_limit)
        .all()
    )
    # Normaliza histórico para o formato aceito pelo modelo.
    history_messages = []
    for msg in reversed(history):
        if msg.role not in {"user", "assistant", "tool"}:
            continue
        if msg.role == "tool":
            history_messages.append({"role": "assistant", "content": f"RESULTADO_SELECT: {msg.content}"})
        else:
            history_messages.append({"role": msg.role, "content": msg.content})
    if agent.allow_db and agent.connection_ids:
        # Usa orquestrador SQL-RAG para consultas com banco externo.
        answer, used_sql, tool_payload = orchestrate_sql_rag(
            db,
            user_message,
            agent.connection_ids,
            history_messages,
            system_prompt,
        )
        return answer, citations, used_sql, tool_payload or None

    messages = [{"role": "system", "content": system_prompt}, *history_messages, {"role": "user", "content": user_message}]
    answer = _call_llm(agent.model, messages)
    return answer, citations, [], None
