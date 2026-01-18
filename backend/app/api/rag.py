from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import RagAskIn, RagAskOut, RagIndexIn
from app.services.rag import reindex_embeddings, ask_rag

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/index")
def index_catalog(payload: RagIndexIn, db: Session = Depends(get_db)):
    count = reindex_embeddings(db, payload.scan_id, payload.include_api_routes)
    return {"indexed": count}


@router.post("/ask", response_model=RagAskOut)
def ask(payload: RagAskIn, db: Session = Depends(get_db)):
    if not payload.question:
        raise HTTPException(status_code=400, detail="Question is required")
    response = ask_rag(db, payload.question)
    return RagAskOut(**response)
