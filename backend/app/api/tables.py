from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import DbTable, DbColumn, Sample
from app.schemas import SampleOut, AnnotationUpdate

router = APIRouter(tags=["tables"])


@router.get("/tables/{table_id}/samples", response_model=list[SampleOut])
def get_samples(table_id: int, db: Session = Depends(get_db)):
    table = db.get(DbTable, table_id)
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    return db.query(Sample).filter(Sample.table_id == table_id).order_by(Sample.id.desc()).all()


@router.put("/tables/{table_id}/annotations")
def update_table_annotations(table_id: int, payload: AnnotationUpdate, db: Session = Depends(get_db)):
    table = db.get(DbTable, table_id)
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    if payload.description is not None:
        table.description = payload.description
    if payload.annotations is not None:
        table.annotations = payload.annotations
    if payload.updated_by is not None:
        table.updated_by = payload.updated_by
    db.commit()
    db.refresh(table)
    return {"status": "updated"}


@router.put("/columns/{column_id}/annotations")
def update_column_annotations(column_id: int, payload: AnnotationUpdate, db: Session = Depends(get_db)):
    column = db.get(DbColumn, column_id)
    if not column:
        raise HTTPException(status_code=404, detail="Column not found")
    if payload.description is not None:
        column.description = payload.description
    if payload.annotations is not None:
        column.annotations = payload.annotations
    if payload.updated_by is not None:
        column.updated_by = payload.updated_by
    db.commit()
    db.refresh(column)
    return {"status": "updated"}
