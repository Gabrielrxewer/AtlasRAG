import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import RagAskIn, RagAskOut, RagIndexIn
from app.services.rag import reindex_embeddings, ask_rag
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
    response = ask_rag(db, question)
    logger.info("rag_ask_completed", extra={"question_length": len(question)})
    return RagAskOut(**response)
