from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import RagAskIn, RagAskOut, RagIndexIn
from app.services.rag import reindex_embeddings, ask_rag
from app import models

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/index")
def index_catalog(payload: RagIndexIn, db: Session = Depends(get_db)):
    if payload.scan_id is not None:
        scan = db.get(models.Scan, payload.scan_id)
        if not scan:
            raise HTTPException(status_code=404, detail="Scan not found")
    count = reindex_embeddings(db, payload.scan_id, payload.include_api_routes)
    return {"indexed": count}


@router.post("/ask", response_model=RagAskOut)
def ask(payload: RagAskIn, db: Session = Depends(get_db)):
    question = payload.question.strip()
    if len(question) < 3:
        raise HTTPException(status_code=400, detail="Question is required")
    response = ask_rag(db, question)
    return RagAskOut(**response)
