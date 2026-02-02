import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Scan, DbTable, DbSchema
from app.schemas import TableSchemaOut
from app.services.selects import build_suggested_selects

router = APIRouter(prefix="/scans", tags=["scans"])
logger = logging.getLogger("atlasrag.scans")


@router.get("/{scan_id}/schema", response_model=list[TableSchemaOut])
def get_scan_schema(scan_id: int, db: Session = Depends(get_db)):
    logger.info("scan_schema_requested", extra={"scan_id": scan_id})
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
    logger.info("scan_schema_tables_loaded", extra={"scan_id": scan_id, "table_count": len(tables)})
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
                suggested_selects=build_suggested_selects(
                    table.schema.name,
                    table.name,
                    [column.name for column in table.columns],
                ),
            )
        )
    logger.info("scan_schema_response_ready", extra={"scan_id": scan_id, "table_count": len(output)})
    return output
