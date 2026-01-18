from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Scan, DbTable, DbSchema
from app.schemas import TableSchemaOut

router = APIRouter(prefix="/scans", tags=["scans"])


@router.get("/{scan_id}/schema", response_model=list[TableSchemaOut])
def get_scan_schema(scan_id: int, db: Session = Depends(get_db)):
    scan = db.get(Scan, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    tables = (
        db.query(DbTable)
        .join(DbTable.schema)
        .filter(DbSchema.scan_id == scan_id)
        .order_by(DbTable.id)
        .all()
    )
    output = []
    for table in tables:
        output.append(
            TableSchemaOut(
                id=table.id,
                schema=table.schema.name,
                name=table.name,
                table_type=table.table_type,
                description=table.description,
                annotations=table.annotations,
                columns=[
                    {
                        "id": column.id,
                        "table_id": table.id,
                        "name": column.name,
                        "data_type": column.data_type,
                        "is_nullable": column.is_nullable,
                        "default": column.default,
                        "description": column.description,
                        "annotations": column.annotations,
                    }
                    for column in table.columns
                ],
            )
        )
    return output
