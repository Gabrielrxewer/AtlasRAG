import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import RagAskIn, RagAskOut, RagIndexIn
from app.services.rag import reindex_embeddings, ask_rag
from app.services.sql_orchestrator import orchestrate_sql_rag
from app import models

router = APIRouter(prefix="/rag", tags=["rag"])
logger = logging.getLogger("atlasrag.rag")


@router.post("/index")
def index_catalog(payload: RagIndexIn, db: Session = Depends(get_db)):
    logger.info(
        "rag_index_requested",
        extra={"scan_id": payload.scan_id, "include_api_routes": payload.include_api_routes},
    )
    if payload.scan_id is not None:
        scan = db.get(models.Scan, payload.scan_id)
        if not scan:
            raise HTTPException(status_code=404, detail="Scan not found")
    count = reindex_embeddings(db, payload.scan_id, payload.include_api_routes)
    logger.info("rag_index_completed", extra={"scan_id": payload.scan_id, "indexed": count})
    return {"indexed": count}


@router.post("/ask", response_model=RagAskOut)
def ask(payload: RagAskIn, db: Session = Depends(get_db)):
    logger.info("rag_ask_requested", extra={"question_length": len(payload.question or "")})
    question = payload.question.strip()
    if len(question) < 3:
        raise HTTPException(status_code=400, detail="Question is required")
    scope = payload.scope.model_dump() if payload.scope else None
    if scope and scope.get("connection_ids"):
        answer, executed, _tool_payload = orchestrate_sql_rag(
            db,
            question,
            scope["connection_ids"],
            [],
            "Você é o assistente do Playground de dados. Responda com base nos dados consultados.",
        )
        logger.info("rag_ask_completed", extra={"question_length": len(question), "mode": "sql"})
        return RagAskOut(answer=answer, citations=[], selects=executed)
    response = ask_rag(db, question, scope=scope)
    logger.info("rag_ask_completed", extra={"question_length": len(question), "mode": "rag"})
    return RagAskOut(**response, selects=[])
