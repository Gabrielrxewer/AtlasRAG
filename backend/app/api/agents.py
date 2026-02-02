import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Agent, AgentMessage, Connection, ApiRoute
from app.schemas import (
    AgentCreate,
    AgentOut,
    AgentUpdate,
    AgentMessageCreate,
    AgentMessageOut,
    AgentChatResponse,
)
from app.services.agents import build_agent_reply

router = APIRouter(prefix="/agents", tags=["agents"])
logger = logging.getLogger("atlasrag.agents")


def _validate_related_ids(db: Session, ids: list[int], model, label: str) -> None:
    if not ids:
        return
    existing = set(db.scalars(select(model.id).where(model.id.in_(ids))).all())
    missing = sorted(set(ids) - existing)
    if missing:
        raise HTTPException(status_code=400, detail=f"{label} not found: {missing}")


@router.post("", response_model=AgentOut)
def create_agent(payload: AgentCreate, db: Session = Depends(get_db)):
    logger.info("agent_create_requested", extra={"name": payload.name})
    _validate_related_ids(db, payload.connection_ids, Connection, "Connections")
    _validate_related_ids(db, payload.api_route_ids, ApiRoute, "API routes")
    agent = Agent(**payload.model_dump())
    db.add(agent)
    db.commit()
    db.refresh(agent)
    logger.info("agent_created", extra={"agent_id": agent.id})
    return agent


@router.get("", response_model=list[AgentOut])
def list_agents(db: Session = Depends(get_db)):
    logger.info("agent_list_requested")
    agents = db.query(Agent).order_by(Agent.id).all()
    logger.info("agent_list_loaded", extra={"agent_count": len(agents)})
    return agents


@router.get("/{agent_id}", response_model=AgentOut)
def get_agent(agent_id: int, db: Session = Depends(get_db)):
    logger.info("agent_get_requested", extra={"agent_id": agent_id})
    agent = db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.put("/{agent_id}", response_model=AgentOut)
def update_agent(agent_id: int, payload: AgentUpdate, db: Session = Depends(get_db)):
    logger.info("agent_update_requested", extra={"agent_id": agent_id})
    agent = db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if payload.connection_ids is not None:
        _validate_related_ids(db, payload.connection_ids, Connection, "Connections")
    if payload.api_route_ids is not None:
        _validate_related_ids(db, payload.api_route_ids, ApiRoute, "API routes")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(agent, key, value)
    db.commit()
    db.refresh(agent)
    logger.info("agent_updated", extra={"agent_id": agent_id})
    return agent


@router.delete("/{agent_id}")
def delete_agent(agent_id: int, db: Session = Depends(get_db)):
    logger.info("agent_delete_requested", extra={"agent_id": agent_id})
    agent = db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    db.delete(agent)
    db.commit()
    logger.info("agent_deleted", extra={"agent_id": agent_id})
    return {"status": "deleted"}


@router.get("/{agent_id}/messages", response_model=list[AgentMessageOut])
def list_agent_messages(agent_id: int, db: Session = Depends(get_db)):
    logger.info("agent_messages_list_requested", extra={"agent_id": agent_id})
    agent = db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    messages = db.query(AgentMessage).filter(AgentMessage.agent_id == agent_id).order_by(AgentMessage.id).all()
    logger.info("agent_messages_list_loaded", extra={"agent_id": agent_id, "message_count": len(messages)})
    return messages


@router.post("/{agent_id}/messages", response_model=AgentChatResponse)
def send_agent_message(agent_id: int, payload: AgentMessageCreate, db: Session = Depends(get_db)):
    logger.info("agent_message_send_requested", extra={"agent_id": agent_id})
    agent = db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    user_message = AgentMessage(agent_id=agent_id, role="user", content=payload.content)
    db.add(user_message)
    db.flush()

    try:
        reply, citations, executed_selects, tool_payload = build_agent_reply(
            db, agent, payload.content, user_message.id
        )
    except RuntimeError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if tool_payload:
        tool_message = AgentMessage(agent_id=agent_id, role="tool", content=tool_payload)
        db.add(tool_message)

    assistant_message = AgentMessage(agent_id=agent_id, role="assistant", content=reply)
    db.add(assistant_message)
    db.commit()
    db.refresh(assistant_message)
    logger.info("agent_message_send_completed", extra={"agent_id": agent_id})
    return AgentChatResponse(message=assistant_message, citations=citations, selects=executed_selects)
