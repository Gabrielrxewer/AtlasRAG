from __future__ import annotations

from typing import Any
import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Agent, Connection, ApiRoute
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


def _build_system_prompt(agent: Agent, connections: list[Connection], routes: list[ApiRoute], context: list[dict[str, Any]]) -> str:
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
    ]
    if agent.rag_prompt:
        lines.append(f"Prompt RAG: {agent.rag_prompt}")
    if agent.enable_rag:
        if context:
            lines.append(f"Contexto RAG: {context}")
        else:
            lines.append("Contexto RAG: nenhum contexto relevante encontrado.")
    return "\n".join(lines)


def build_agent_reply(db: Session, agent: Agent, user_message: str) -> tuple[str, list[dict[str, Any]]]:
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
        matches = search_embeddings(db, user_message.strip(), settings.rag_top_k)
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
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]
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

    answer = data["choices"][0]["message"]["content"]
    return answer, citations
