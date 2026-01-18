from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import re
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.engine import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from app.models import DbSchema, DbTable, DbColumn, DbConstraint, DbIndex, DbView, Sample, Scan


@dataclass
class ConnectionInfo:
    host: str
    port: int
    database: str
    username: str
    password: str
    ssl_mode: str


SCHEMA_QUERY = """
SELECT schema_name
FROM information_schema.schemata
WHERE schema_name NOT IN ('pg_catalog', 'information_schema')
ORDER BY schema_name;
"""

TABLE_QUERY = """
SELECT table_schema, table_name, table_type
FROM information_schema.tables
WHERE table_schema = :schema_name
ORDER BY table_name;
"""

COLUMN_QUERY = """
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema = :schema_name AND table_name = :table_name
ORDER BY ordinal_position;
"""

CONSTRAINT_QUERY = """
SELECT con.conname AS name,
       con.contype AS type,
       pg_get_constraintdef(con.oid) AS definition
FROM pg_constraint con
JOIN pg_class rel ON rel.oid = con.conrelid
JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
WHERE nsp.nspname = :schema_name
  AND rel.relname = :table_name;
"""

INDEX_QUERY = """
SELECT indexname, indexdef
FROM pg_indexes
WHERE schemaname = :schema_name AND tablename = :table_name;
"""

VIEW_QUERY = """
SELECT table_name, view_definition
FROM information_schema.views
WHERE table_schema = :schema_name
ORDER BY table_name;
"""

PRIMARY_KEY_QUERY = """
SELECT a.attname AS column_name
FROM pg_index i
JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
JOIN pg_class c ON c.oid = i.indrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE i.indisprimary
  AND n.nspname = :schema_name
  AND c.relname = :table_name;
"""

IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def is_safe_identifier(value: str) -> bool:
    return bool(IDENTIFIER_RE.match(value))


def build_sample_query(schema_name: str, table_name: str, pk_columns: list[str]) -> str | None:
    if not (is_safe_identifier(schema_name) and is_safe_identifier(table_name)):
        return None
    for column in pk_columns:
        if not is_safe_identifier(column):
            return None
    order_by = ""
    if pk_columns:
        pk_list = ", ".join(pk_columns)
        order_by = f" ORDER BY {pk_list}"
    return f"SELECT * FROM {schema_name}.{table_name}{order_by} LIMIT :limit"


def _build_client_engine(info: ConnectionInfo):
    url = URL.create(
        "postgresql+psycopg2",
        username=info.username,
        password=info.password,
        host=info.host,
        port=info.port,
        database=info.database,
        query={"sslmode": info.ssl_mode},
    )
    return create_engine(url, pool_pre_ping=True)


def test_connection(info: ConnectionInfo) -> None:
    engine = _build_client_engine(info)
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))


def run_scan(db: Session, connection_info: ConnectionInfo, scan_id: int, sample_limit: int = 20) -> None:
    scan = db.get(Scan, scan_id)
    if scan:
        if scan.status != "running":
            scan.status = "running"
        if scan.started_at is None:
            scan.started_at = datetime.utcnow()
        db.commit()
        existing_schemas = db.query(DbSchema).filter(DbSchema.scan_id == scan_id).all()
        for schema in existing_schemas:
            db.delete(schema)
        if existing_schemas:
            db.commit()

    client_engine = _build_client_engine(connection_info)
    try:
        with client_engine.connect() as conn:
            schemas = conn.execute(text(SCHEMA_QUERY)).fetchall()
            for (schema_name,) in schemas:
                schema = DbSchema(scan_id=scan_id, name=schema_name)
                db.add(schema)
                db.flush()

                views = conn.execute(text(VIEW_QUERY), {"schema_name": schema_name}).fetchall()
                for view_name, definition in views:
                    db.add(DbView(schema_id=schema.id, name=view_name, definition=definition))

                tables = conn.execute(text(TABLE_QUERY), {"schema_name": schema_name}).fetchall()
                for table_schema, table_name, table_type in tables:
                    table = DbTable(schema_id=schema.id, name=table_name, table_type=table_type)
                    db.add(table)
                    db.flush()

                    columns = conn.execute(
                        text(COLUMN_QUERY), {"schema_name": table_schema, "table_name": table_name}
                    ).fetchall()
                    for column_name, data_type, is_nullable, column_default in columns:
                        db.add(
                            DbColumn(
                                table_id=table.id,
                                name=column_name,
                                data_type=data_type,
                                is_nullable=is_nullable == "YES",
                                default=column_default,
                            )
                        )

                    constraints = conn.execute(
                        text(CONSTRAINT_QUERY), {"schema_name": table_schema, "table_name": table_name}
                    ).fetchall()
                    for name, constraint_type, definition in constraints:
                        db.add(
                            DbConstraint(
                                table_id=table.id,
                                name=name,
                                constraint_type=constraint_type,
                                definition=definition,
                            )
                        )

                    indexes = conn.execute(
                        text(INDEX_QUERY), {"schema_name": table_schema, "table_name": table_name}
                    ).fetchall()
                    for index_name, definition in indexes:
                        db.add(DbIndex(table_id=table.id, name=index_name, definition=definition))

                    sample_rows = _fetch_samples(conn, table_schema, table_name, sample_limit)
                    if sample_rows:
                        db.add(Sample(table_id=table.id, rows=sample_rows))

        if scan:
            scan.status = "completed"
            scan.finished_at = datetime.utcnow()
        db.commit()
    except Exception:
        if scan:
            scan.status = "failed"
            scan.finished_at = datetime.utcnow()
            db.commit()
        raise


def _fetch_samples(conn, schema_name: str, table_name: str, sample_limit: int) -> list[dict[str, Any]]:
    pk_columns = [
        row[0]
        for row in conn.execute(text(PRIMARY_KEY_QUERY), {"schema_name": schema_name, "table_name": table_name})
    ]
    query_text = build_sample_query(schema_name, table_name, pk_columns)
    if not query_text:
        return []
    query = text(query_text)
    result = conn.execute(query, {"limit": sample_limit})
    columns = result.keys()
    return [dict(zip(columns, row)) for row in result.fetchall()]
