from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import re
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.engine import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

import logging

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
logger = logging.getLogger("atlasrag.scan")


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


def _truncate_log_value(value: str, limit: int = 120) -> str:
    if len(value) <= limit:
        return value
    return f"{value[:limit]}…({len(value)} chars)"


def _coerce_text(
    value: Any,
    *,
    scan_id: int,
    object_type: str,
    field_name: str,
    schema_name: str | None = None,
    table_name: str | None = None,
) -> Any:
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            for encoding in ("cp1252", "latin-1"):
                try:
                    decoded = value.decode(encoding, errors="strict")
                    logger.warning(
                        "scan_text_decode_fallback",
                        extra={
                            "scan_id": scan_id,
                            "object_type": object_type,
                            "field_name": field_name,
                            "schema_name": schema_name,
                            "table_name": table_name,
                            "encoding": encoding,
                            "value_sample": _truncate_log_value(decoded),
                            "value_length": len(value),
                        },
                    )
                    return decoded
                except UnicodeDecodeError:
                    continue
            decoded = value.decode("utf-8", errors="replace")
            logger.warning(
                "scan_text_decode_replaced",
                extra={
                    "scan_id": scan_id,
                    "object_type": object_type,
                    "field_name": field_name,
                    "schema_name": schema_name,
                    "table_name": table_name,
                    "value_sample": _truncate_log_value(decoded),
                    "value_length": len(value),
                },
            )
            return decoded
    return value


def _coerce_sample_value(value: Any, *, scan_id: int, schema_name: str, table_name: str, column_name: str) -> Any:
    return _coerce_text(
        value,
        scan_id=scan_id,
        object_type="sample",
        field_name=column_name,
        schema_name=schema_name,
        table_name=table_name,
    )


def _configure_client_encoding(conn, scan_id: int) -> None:
    try:
        conn.execute(text("SET client_encoding TO 'UTF8'"))
    except Exception:
        logger.warning("scan_client_encoding_set_failed", extra={"scan_id": scan_id}, exc_info=True)


def _log_postgres_encodings(conn, scan_id: int) -> None:
    try:
        server_encoding = conn.execute(text("SHOW server_encoding")).scalar_one_or_none()
        client_encoding = conn.execute(text("SHOW client_encoding")).scalar_one_or_none()
        logger.info(
            "scan_db_encoding",
            extra={
                "scan_id": scan_id,
                "server_encoding": server_encoding,
                "client_encoding": client_encoding,
            },
        )
    except Exception:
        logger.debug("scan_db_encoding_failed", extra={"scan_id": scan_id}, exc_info=True)


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
            scan.started_at = datetime.now(timezone.utc)
        scan.error_message = None
        db.commit()
        existing_schemas = db.query(DbSchema).filter(DbSchema.scan_id == scan_id).all()
        for schema in existing_schemas:
            db.delete(schema)
        if existing_schemas:
            db.commit()

    client_engine = _build_client_engine(connection_info)
    logger.info(
        "scan_started",
        extra={
            "scan_id": scan_id,
            "host": connection_info.host,
            "port": connection_info.port,
            "database": connection_info.database,
            "ssl_mode": connection_info.ssl_mode,
        },
    )
    try:
        with client_engine.connect() as conn:
            _configure_client_encoding(conn, scan_id)
            _log_postgres_encodings(conn, scan_id)
            schemas = conn.execute(text(SCHEMA_QUERY)).fetchall()
            logger.info("scan_schemas_loaded", extra={"scan_id": scan_id, "schema_count": len(schemas)})
            for (schema_name,) in schemas:
                schema_name = _coerce_text(
                    schema_name,
                    scan_id=scan_id,
                    object_type="schema",
                    field_name="name",
                )
                schema = DbSchema(scan_id=scan_id, name=schema_name)
                db.add(schema)
                db.flush()

                views = conn.execute(text(VIEW_QUERY), {"schema_name": schema_name}).fetchall()
                logger.info(
                    "scan_views_loaded",
                    extra={"scan_id": scan_id, "schema_name": schema_name, "view_count": len(views)},
                )
                for view_name, definition in views:
                    view_name = _coerce_text(
                        view_name,
                        scan_id=scan_id,
                        object_type="view",
                        field_name="name",
                        schema_name=schema_name,
                    )
                    definition = _coerce_text(
                        definition,
                        scan_id=scan_id,
                        object_type="view",
                        field_name="definition",
                        schema_name=schema_name,
                    )
                    db.add(DbView(schema_id=schema.id, name=view_name, definition=definition))

                tables = conn.execute(text(TABLE_QUERY), {"schema_name": schema_name}).fetchall()
                logger.info(
                    "scan_tables_loaded",
                    extra={"scan_id": scan_id, "schema_name": schema_name, "table_count": len(tables)},
                )
                for table_schema, table_name, table_type in tables:
                    table_schema = _coerce_text(
                        table_schema,
                        scan_id=scan_id,
                        object_type="table",
                        field_name="schema",
                    )
                    table_name = _coerce_text(
                        table_name,
                        scan_id=scan_id,
                        object_type="table",
                        field_name="name",
                        schema_name=table_schema,
                    )
                    table_type = _coerce_text(
                        table_type,
                        scan_id=scan_id,
                        object_type="table",
                        field_name="type",
                        schema_name=table_schema,
                        table_name=table_name,
                    )
                    table = DbTable(schema_id=schema.id, name=table_name, table_type=table_type)
                    db.add(table)
                    db.flush()

                    columns = conn.execute(
                        text(COLUMN_QUERY), {"schema_name": table_schema, "table_name": table_name}
                    ).fetchall()
                    logger.info(
                        "scan_columns_loaded",
                        extra={
                            "scan_id": scan_id,
                            "schema_name": table_schema,
                            "table_name": table_name,
                            "column_count": len(columns),
                        },
                    )
                    for column_name, data_type, is_nullable, column_default in columns:
                        column_name = _coerce_text(
                            column_name,
                            scan_id=scan_id,
                            object_type="column",
                            field_name="name",
                            schema_name=table_schema,
                            table_name=table_name,
                        )
                        data_type = _coerce_text(
                            data_type,
                            scan_id=scan_id,
                            object_type="column",
                            field_name="data_type",
                            schema_name=table_schema,
                            table_name=table_name,
                        )
                        is_nullable = _coerce_text(
                            is_nullable,
                            scan_id=scan_id,
                            object_type="column",
                            field_name="is_nullable",
                            schema_name=table_schema,
                            table_name=table_name,
                        )
                        column_default = _coerce_text(
                            column_default,
                            scan_id=scan_id,
                            object_type="column",
                            field_name="default",
                            schema_name=table_schema,
                            table_name=table_name,
                        )
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
                    logger.info(
                        "scan_constraints_loaded",
                        extra={
                            "scan_id": scan_id,
                            "schema_name": table_schema,
                            "table_name": table_name,
                            "constraint_count": len(constraints),
                        },
                    )
                    for name, constraint_type, definition in constraints:
                        name = _coerce_text(
                            name,
                            scan_id=scan_id,
                            object_type="constraint",
                            field_name="name",
                            schema_name=table_schema,
                            table_name=table_name,
                        )
                        constraint_type = _coerce_text(
                            constraint_type,
                            scan_id=scan_id,
                            object_type="constraint",
                            field_name="type",
                            schema_name=table_schema,
                            table_name=table_name,
                        )
                        definition = _coerce_text(
                            definition,
                            scan_id=scan_id,
                            object_type="constraint",
                            field_name="definition",
                            schema_name=table_schema,
                            table_name=table_name,
                        )
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
                    logger.info(
                        "scan_indexes_loaded",
                        extra={
                            "scan_id": scan_id,
                            "schema_name": table_schema,
                            "table_name": table_name,
                            "index_count": len(indexes),
                        },
                    )
                    for index_name, definition in indexes:
                        index_name = _coerce_text(
                            index_name,
                            scan_id=scan_id,
                            object_type="index",
                            field_name="name",
                            schema_name=table_schema,
                            table_name=table_name,
                        )
                        definition = _coerce_text(
                            definition,
                            scan_id=scan_id,
                            object_type="index",
                            field_name="definition",
                            schema_name=table_schema,
                            table_name=table_name,
                        )
                        db.add(DbIndex(table_id=table.id, name=index_name, definition=definition))

                    sample_rows = _fetch_samples(conn, table_schema, table_name, sample_limit, scan_id=scan_id)
                    if sample_rows:
                        db.add(Sample(table_id=table.id, rows=sample_rows))
                    logger.info(
                        "scan_samples_loaded",
                        extra={
                            "scan_id": scan_id,
                            "schema_name": table_schema,
                            "table_name": table_name,
                            "sample_count": len(sample_rows),
                        },
                    )

        if scan:
            scan.status = "completed"
            scan.finished_at = datetime.now(timezone.utc)
            scan.error_message = None
        db.commit()
        logger.info("scan_completed", extra={"scan_id": scan_id})
    except Exception as exc:
        logger.exception("scan_failed", extra={"scan_id": scan_id})
        if scan:
            scan.status = "failed"
            scan.finished_at = datetime.now(timezone.utc)
            scan.error_message = f"{type(exc).__name__}: {exc}"[:1000]
            db.commit()
        raise


def _fetch_samples(
    conn, schema_name: str, table_name: str, sample_limit: int, *, scan_id: int
) -> list[dict[str, Any]]:
    pk_columns = [
        _coerce_text(
            row[0],
            scan_id=scan_id,
            object_type="primary_key",
            field_name="column_name",
            schema_name=schema_name,
            table_name=table_name,
        )
        for row in conn.execute(text(PRIMARY_KEY_QUERY), {"schema_name": schema_name, "table_name": table_name})
    ]
    query_text = build_sample_query(schema_name, table_name, pk_columns)
    if not query_text:
        logger.warning(
            "scan_sample_query_invalid",
            extra={"schema_name": schema_name, "table_name": table_name},
        )
        return []
    query = text(query_text)
    try:
        result = conn.execute(query, {"limit": sample_limit})
        columns = result.keys()
        rows = []
        for row in result.fetchall():
            rows.append(
                {
                    column_name: _coerce_sample_value(
                        value,
                        scan_id=scan_id,
                        schema_name=schema_name,
                        table_name=table_name,
                        column_name=column_name,
                    )
                    for column_name, value in zip(columns, row)
                }
            )
        return rows
    except Exception:
        logger.exception(
            "scan_sample_query_failed",
            extra={"schema_name": schema_name, "table_name": table_name},
        )
        return []
