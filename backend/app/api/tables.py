import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import DbTable, DbColumn, Sample
from app.schemas import SampleOut, AnnotationUpdate

router = APIRouter(tags=["tables"])
logger = logging.getLogger("atlasrag.tables")


@router.get("/tables/{table_id}/samples", response_model=list[SampleOut])
def get_samples(table_id: int, db: Session = Depends(get_db)):
    logger.info("table_samples_requested", extra={"table_id": table_id})
    table = db.get(DbTable, table_id)
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    samples = db.query(Sample).filter(Sample.table_id == table_id).order_by(Sample.id.desc()).all()
    logger.info("table_samples_loaded", extra={"table_id": table_id, "sample_count": len(samples)})
    return samples


@router.put("/tables/{table_id}/annotations")
def update_table_annotations(table_id: int, payload: AnnotationUpdate, db: Session = Depends(get_db)):
    logger.info("table_annotations_update_requested", extra={"table_id": table_id})
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
    logger.info("table_annotations_updated", extra={"table_id": table_id})
    return {"status": "updated"}


@router.put("/columns/{column_id}/annotations")
def update_column_annotations(column_id: int, payload: AnnotationUpdate, db: Session = Depends(get_db)):
    logger.info("column_annotations_update_requested", extra={"column_id": column_id})
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
    logger.info("column_annotations_updated", extra={"column_id": column_id})
    return {"status": "updated"}
