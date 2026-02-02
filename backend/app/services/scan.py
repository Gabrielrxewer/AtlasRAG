import logging
import os
import re
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import URL, create_engine
from sqlalchemy.orm import Session

from app.models import DbColumn, DbConstraint, DbIndex, DbSchema, DbTable, DbView, Sample, Scan

logger = logging.getLogger("atlasrag")

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

DB_ENCODING_QUERY = """
SELECT pg_encoding_to_char(encoding)
FROM pg_database
WHERE datname = current_database();
"""

ENCODING_NAME_RE = re.compile(r"^[A-Za-z0-9_]+$")
IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


@dataclass
class ConnectionInfo:
    host: str
    port: int
    database: str
    username: str
    password: str
    ssl_mode: str
    client_encoding: str | None = None
    pgclientencoding: str | None = None


@dataclass
class ScanContext:
    scan_id: int
    step: str = "init"
    context: str = "-"
    schema_name: str | None = None
    table_name: str | None = None
    query: str | None = None
    params: dict[str, Any] | None = None

    def as_log_extra(self) -> dict[str, Any]:
        return {
            "scan_id": self.scan_id,
            "step": self.step,
            "context": self.context,
            "schema_name": self.schema_name,
            "table_name": self.table_name,
        }

    def format_compact(self) -> str:
        s = self.schema_name or "-"
        t = self.table_name or "-"
        return f"step={self.step} context={self.context} schema={s} table={t}"


def _truncate(value: str, limit: int) -> str:
    if value is None:
        return ""
    if len(value) <= limit:
        return value
    return f"{value[:limit]}…({len(value)} chars)"


def _ensure_text_clause(query: str | Any):
    if isinstance(query, str):
        return text(query)
    return query


def _decode_bytes(b: bytes) -> str:
    for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            pass
    return b.decode("utf-8", errors="replace")


def _safe_obj(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, (bytes, bytearray, memoryview)):
        return _decode_bytes(bytes(v))
    if isinstance(v, dict):
        return {str(_safe_obj(k)): _safe_obj(val) for k, val in v.items()}
    if isinstance(v, list):
        return [_safe_obj(x) for x in v]
    if isinstance(v, tuple):
        return tuple(_safe_obj(x) for x in v)
    return v


def _safe_str(exc: BaseException) -> str:
    try:
        s = str(exc)
        return s
    except Exception:
        try:
            return repr(exc)
        except Exception:
            return "<unprintable-exception>"


def _safe_tb(exc: BaseException) -> str:
    try:
        tb = "".join(traceback.format_tb(exc.__traceback__))
        return tb
    except Exception:
        return ""


def _is_encoding_related_error(exc: Exception) -> bool:
    if isinstance(exc, UnicodeError):
        return True
    msg = _safe_str(exc).lower()
    needles = (
        "unicodedecodeerror",
        "unicodeencodeerror",
        "invalid byte sequence for encoding",
        "has no equivalent in encoding",
        "codec can't decode",
        "character with byte sequence",
    )
    return any(n in msg for n in needles)


def _get_client_encoding(conn) -> str | None:
    try:
        v = conn.execute(text("SHOW client_encoding")).scalar_one_or_none()
        return v if isinstance(v, str) else None
    except Exception:
        return None


def _get_server_encoding(conn) -> str | None:
    try:
        v = conn.execute(text("SHOW server_encoding")).scalar_one_or_none()
        return v if isinstance(v, str) else None
    except Exception:
        return None


def _get_db_encoding(conn) -> str | None:
    try:
        v = conn.execute(text(DB_ENCODING_QUERY)).scalar_one_or_none()
        return v if isinstance(v, str) else None
    except Exception:
        return None


def _set_client_encoding(conn, *, scan_id: int, encoding: str, reason: str) -> None:
    if not ENCODING_NAME_RE.fullmatch(encoding):
        logger.warning(
            "scan_client_encoding_invalid_name",
            extra={"scan_id": scan_id, "encoding": encoding, "reason": reason},
        )
        return
    try:
        conn.exec_driver_sql(f"SET client_encoding TO '{encoding}'")
        logger.info(
            "scan_client_encoding_set",
            extra={
                "scan_id": scan_id,
                "requested": encoding,
                "current": _get_client_encoding(conn),
                "reason": reason,
            },
        )
    except Exception as e:
        logger.warning(
            "scan_client_encoding_set_failed",
            extra={"scan_id": scan_id, "encoding": encoding, "reason": reason, "error": _safe_str(e)},
            exc_info=True,
        )


def _detect_preferred_encoding(conn) -> str:
    se = (_get_server_encoding(conn) or "").upper()
    de = (_get_db_encoding(conn) or "").upper()
    if se == "SQL_ASCII" or de == "SQL_ASCII":
        return "WIN1252"
    if se:
        return se
    return "UTF8"


def _with_pgclientencoding(value: str | None):
    class _Ctx:
        def __init__(self, v: str | None):
            self.v = v
            self.prev = None

        def __enter__(self):
            if not self.v:
                return
            self.prev = os.environ.get("PGCLIENTENCODING")
            os.environ["PGCLIENTENCODING"] = self.v

        def __exit__(self, exc_type, exc, tb):
            if not self.v:
                return False
            if self.prev is None:
                os.environ.pop("PGCLIENTENCODING", None)
            else:
                os.environ["PGCLIENTENCODING"] = self.prev
            return False

    return _Ctx(value)


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
    connect_args: dict[str, Any] = {}
    if info.client_encoding and ENCODING_NAME_RE.fullmatch(info.client_encoding):
        connect_args["options"] = f"-c client_encoding={info.client_encoding}"
    return create_engine(url, pool_pre_ping=True, connect_args=connect_args)


def _checkpoint(db: Session, ctx: ScanContext) -> None:
    logger.info("scan_checkpoint", extra=ctx.as_log_extra())
    try:
        scan = db.get(Scan, ctx.scan_id)
        if not scan:
            return
        msg = f"checkpoint: {ctx.format_compact()}"
        scan.error_message = _truncate(msg, 2000)
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass


def _fail_with_context(db: Session, ctx: ScanContext, exc: Exception) -> None:
    err = _safe_str(exc)
    tb = _safe_tb(exc)
    query = _safe_obj(ctx.query or "")
    params = _safe_obj(ctx.params or {})

    logger.error(
        "scan_failed_with_context",
        extra={
            **ctx.as_log_extra(),
            "query": _truncate(str(query), 1200),
            "params": _truncate(str(params), 600),
            "error": _truncate(err, 1200),
        },
        exc_info=True,
    )

    try:
        scan = db.get(Scan, ctx.scan_id)
        if scan:
            detail = (
                f"{type(exc).__name__} at {ctx.format_compact()} "
                f"query={_truncate(str(query), 1800)} "
                f"params={_truncate(str(params), 1200)} "
                f"error={_truncate(err, 1800)}\n{tb}"
            )
            scan.status = "failed"
            scan.finished_at = datetime.now(timezone.utc)
            scan.error_message = _truncate(detail, 20000)
            db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass


def is_safe_identifier(value: str) -> bool:
    return bool(IDENTIFIER_RE.match(value))


def build_sample_query(schema_name: str, table_name: str, pk_columns: list[str]) -> str | None:
    if not (is_safe_identifier(schema_name) and is_safe_identifier(table_name)):
        return None
    for column in pk_columns:
        if not is_safe_identifier(column):
            return None

    def q(ident: str) -> str:
        return f'"{ident}"'

    order_by = ""
    if pk_columns:
        pk_list = ", ".join(q(c) for c in pk_columns)
        order_by = f" ORDER BY {pk_list}"

    return f"SELECT * FROM {q(schema_name)}.{q(table_name)}{order_by} LIMIT :limit"


def _coerce_text(value: Any) -> Any:
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, (bytes, bytearray, memoryview)):
        return _decode_bytes(bytes(value))
    return value


def _fetchall(conn, ctx: ScanContext, query: str | Any, params: dict[str, Any] | None) -> list[Any]:
    ctx.query = str(query) if isinstance(query, str) else str(query)
    ctx.params = params or {}
    q = _ensure_text_clause(query)

    logger.info(
        "scan_query_start",
        extra={
            **ctx.as_log_extra(),
            "client_encoding": _get_client_encoding(conn),
            "server_encoding": _get_server_encoding(conn),
            "db_encoding": _get_db_encoding(conn),
            "query": _truncate(ctx.query, 1200),
            "params": _truncate(str(_safe_obj(ctx.params)), 600),
        },
    )

    rows = conn.execute(q, params or {}).fetchall()

    logger.info(
        "scan_query_success",
        extra={
            **ctx.as_log_extra(),
            "row_count": len(rows),
            "client_encoding": _get_client_encoding(conn),
        },
    )
    return rows


def _fetch_rows(conn, ctx: ScanContext, query: str | Any, params: dict[str, Any] | None) -> tuple[list[str], list[Any]]:
    ctx.query = str(query) if isinstance(query, str) else str(query)
    ctx.params = params or {}
    q = _ensure_text_clause(query)

    logger.info(
        "scan_queryrows_start",
        extra={
            **ctx.as_log_extra(),
            "client_encoding": _get_client_encoding(conn),
            "query": _truncate(ctx.query, 1200),
            "params": _truncate(str(_safe_obj(ctx.params)), 600),
        },
    )

    result = conn.execute(q, params or {})
    rows = result.fetchall()
    cols = list(result.keys())

    logger.info(
        "scan_queryrows_success",
        extra={
            **ctx.as_log_extra(),
            "row_count": len(rows),
            "column_count": len(cols),
            "client_encoding": _get_client_encoding(conn),
        },
    )
    return cols, rows


def test_connection(info: ConnectionInfo) -> None:
    with _with_pgclientencoding(info.pgclientencoding):
        engine = _build_client_engine(info)
        with engine.connect() as conn:
            _set_client_encoding(conn, scan_id=0, encoding=_detect_preferred_encoding(conn), reason="test_connection")
            conn.execute(text("SELECT 1"))


def run_scan(db: Session, connection_info: ConnectionInfo, scan_id: int, sample_limit: int = 20) -> None:
    scan = db.get(Scan, scan_id)
    if scan:
        scan.status = "running"
        if scan.started_at is None:
            scan.started_at = datetime.now(timezone.utc)
        scan.finished_at = None
        scan.error_message = None
        db.commit()

    ctx = ScanContext(scan_id=scan_id)
    _checkpoint(db, ctx)

    attempts = [
        ConnectionInfo(**{**connection_info.__dict__, "client_encoding": None, "pgclientencoding": None}),
        ConnectionInfo(**{**connection_info.__dict__, "client_encoding": "UTF8", "pgclientencoding": "UTF8"}),
        ConnectionInfo(**{**connection_info.__dict__, "client_encoding": "WIN1252", "pgclientencoding": "WIN1252"}),
        ConnectionInfo(**{**connection_info.__dict__, "client_encoding": "LATIN1", "pgclientencoding": "LATIN1"}),
    ]

    last_exc: Exception | None = None

    for idx, info in enumerate(attempts, start=1):
        try:
            _run_scan_once(db, info, ctx, sample_limit=sample_limit)
            scan = db.get(Scan, scan_id)
            if scan:
                scan.status = "completed"
                scan.finished_at = datetime.now(timezone.utc)
                scan.error_message = None
                db.commit()
            logger.info("scan_completed", extra={"scan_id": scan_id})
            return
        except Exception as exc:
            last_exc = exc
            if not _is_encoding_related_error(exc) or idx == len(attempts):
                _fail_with_context(db, ctx, exc)
                raise

            next_enc = attempts[idx].pgclientencoding if idx < len(attempts) else None
            logger.warning(
                "scan_retry_due_to_encoding",
                extra={
                    "scan_id": scan_id,
                    "attempt": idx,
                    "next_pgclientencoding": next_enc,
                    "error": _truncate(_safe_str(exc), 1200),
                    **ctx.as_log_extra(),
                },
                exc_info=True,
            )
            try:
                db.rollback()
            except Exception:
                pass

    if last_exc:
        raise last_exc
    raise RuntimeError("scan_failed_without_exception")


def _cleanup_existing_scan_data(db: Session, scan_id: int) -> None:
    db.execute(
        text(
            """
            WITH target_schemas AS (
              SELECT id FROM db_schemas WHERE scan_id = :scan_id
            ),
            target_tables AS (
              SELECT t.id
              FROM db_tables t
              JOIN target_schemas s ON s.id = t.schema_id
            )
            DELETE FROM samples WHERE table_id IN (SELECT id FROM target_tables);
            """
        ),
        {"scan_id": scan_id},
    )
    db.execute(
        text(
            """
            WITH target_schemas AS (
              SELECT id FROM db_schemas WHERE scan_id = :scan_id
            ),
            target_tables AS (
              SELECT t.id
              FROM db_tables t
              JOIN target_schemas s ON s.id = t.schema_id
            )
            DELETE FROM db_columns WHERE table_id IN (SELECT id FROM target_tables);
            """
        ),
        {"scan_id": scan_id},
    )
    db.execute(
        text(
            """
            WITH target_schemas AS (
              SELECT id FROM db_schemas WHERE scan_id = :scan_id
            ),
            target_tables AS (
              SELECT t.id
              FROM db_tables t
              JOIN target_schemas s ON s.id = t.schema_id
            )
            DELETE FROM db_constraints WHERE table_id IN (SELECT id FROM target_tables);
            """
        ),
        {"scan_id": scan_id},
    )
    db.execute(
        text(
            """
            WITH target_schemas AS (
              SELECT id FROM db_schemas WHERE scan_id = :scan_id
            ),
            target_tables AS (
              SELECT t.id
              FROM db_tables t
              JOIN target_schemas s ON s.id = t.schema_id
            )
            DELETE FROM db_indexes WHERE table_id IN (SELECT id FROM target_tables);
            """
        ),
        {"scan_id": scan_id},
    )
    db.execute(
        text(
            """
            WITH target_schemas AS (
              SELECT id FROM db_schemas WHERE scan_id = :scan_id
            )
            DELETE FROM db_views WHERE schema_id IN (SELECT id FROM target_schemas);
            """
        ),
        {"scan_id": scan_id},
    )
    db.execute(
        text(
            """
            WITH target_schemas AS (
              SELECT id FROM db_schemas WHERE scan_id = :scan_id
            )
            DELETE FROM db_tables WHERE schema_id IN (SELECT id FROM target_schemas);
            """
        ),
        {"scan_id": scan_id},
    )
    db.execute(text("DELETE FROM db_schemas WHERE scan_id = :scan_id"), {"scan_id": scan_id})
    db.commit()


def _run_scan_once(db: Session, info: ConnectionInfo, ctx: ScanContext, sample_limit: int) -> None:
    ctx.step = "cleanup"
    ctx.context = "cleanup"
    ctx.schema_name = None
    ctx.table_name = None
    ctx.query = None
    ctx.params = None
    _checkpoint(db, ctx)

    logger.info("scan_cleanup_start", extra={"scan_id": ctx.scan_id})
    _cleanup_existing_scan_data(db, ctx.scan_id)
    logger.info("scan_cleanup_done", extra={"scan_id": ctx.scan_id})

    ctx.step = "connect"
    ctx.context = "connect"
    _checkpoint(db, ctx)

    with _with_pgclientencoding(info.pgclientencoding):
        engine = _build_client_engine(info)

        logger.info(
            "scan_connect_attempt",
            extra={
                "scan_id": ctx.scan_id,
                "host": info.host,
                "port": info.port,
                "database": info.database,
                "ssl_mode": info.ssl_mode,
                "forced_client_encoding": info.client_encoding,
                "forced_pgclientencoding": info.pgclientencoding,
            },
        )

        with engine.connect() as conn:
            ctx.step = "configure_encoding"
            ctx.context = "configure_encoding"
            _checkpoint(db, ctx)

            preferred = _detect_preferred_encoding(conn)
            _set_client_encoding(conn, scan_id=ctx.scan_id, encoding=preferred, reason="scan_start")
            if info.client_encoding:
                _set_client_encoding(conn, scan_id=ctx.scan_id, encoding=info.client_encoding, reason="forced_attempt")

            logger.info(
                "scan_encodings",
                extra={
                    "scan_id": ctx.scan_id,
                    "server_encoding": _get_server_encoding(conn),
                    "client_encoding": _get_client_encoding(conn),
                    "db_encoding": _get_db_encoding(conn),
                },
            )

            ctx.step = "schemas"
            ctx.context = "schemas"
            ctx.schema_name = None
            ctx.table_name = None
            _checkpoint(db, ctx)

            schemas = _fetchall(conn, ctx, SCHEMA_QUERY, None)

            for (schema_name_raw,) in schemas:
                schema_name = _coerce_text(schema_name_raw)
                ctx.schema_name = schema_name
                ctx.table_name = None

                ctx.step = "schema_persist"
                ctx.context = "schema_persist"
                _checkpoint(db, ctx)

                schema = DbSchema(scan_id=ctx.scan_id, name=schema_name)
                db.add(schema)
                db.flush()

                ctx.step = "views"
                ctx.context = "views"
                _checkpoint(db, ctx)

                views = _fetchall(conn, ctx, VIEW_QUERY, {"schema_name": schema_name})
                for view_name_raw, definition_raw in views:
                    view_name = _coerce_text(view_name_raw)
                    definition = _coerce_text(definition_raw)
                    db.add(DbView(schema_id=schema.id, name=view_name, definition=definition))

                ctx.step = "tables"
                ctx.context = "tables"
                _checkpoint(db, ctx)

                tables = _fetchall(conn, ctx, TABLE_QUERY, {"schema_name": schema_name})
                for table_schema_raw, table_name_raw, table_type_raw in tables:
                    table_schema = _coerce_text(table_schema_raw)
                    table_name = _coerce_text(table_name_raw)
                    table_type = _coerce_text(table_type_raw)

                    ctx.schema_name = table_schema
                    ctx.table_name = table_name

                    ctx.step = "table_persist"
                    ctx.context = "table_persist"
                    _checkpoint(db, ctx)

                    table = DbTable(schema_id=schema.id, name=table_name, table_type=table_type)
                    db.add(table)
                    db.flush()

                    ctx.step = "columns"
                    ctx.context = "columns"
                    _checkpoint(db, ctx)

                    columns = _fetchall(
                        conn,
                        ctx,
                        COLUMN_QUERY,
                        {"schema_name": table_schema, "table_name": table_name},
                    )
                    for column_name_raw, data_type_raw, is_nullable_raw, column_default_raw in columns:
                        column_name = _coerce_text(column_name_raw)
                        data_type = _coerce_text(data_type_raw)
                        is_nullable = _coerce_text(is_nullable_raw)
                        column_default = _coerce_text(column_default_raw)

                        db.add(
                            DbColumn(
                                table_id=table.id,
                                name=column_name,
                                data_type=data_type,
                                is_nullable=is_nullable == "YES",
                                default=column_default,
                            )
                        )

                    ctx.step = "constraints"
                    ctx.context = "constraints"
                    _checkpoint(db, ctx)

                    constraints = _fetchall(
                        conn,
                        ctx,
                        CONSTRAINT_QUERY,
                        {"schema_name": table_schema, "table_name": table_name},
                    )
                    for name_raw, constraint_type_raw, definition_raw in constraints:
                        name = _coerce_text(name_raw)
                        constraint_type = _coerce_text(constraint_type_raw)
                        definition = _coerce_text(definition_raw)
                        db.add(
                            DbConstraint(
                                table_id=table.id,
                                name=name,
                                constraint_type=constraint_type,
                                definition=definition,
                            )
                        )

                    ctx.step = "indexes"
                    ctx.context = "indexes"
                    _checkpoint(db, ctx)

                    indexes = _fetchall(
                        conn,
                        ctx,
                        INDEX_QUERY,
                        {"schema_name": table_schema, "table_name": table_name},
                    )
                    for index_name_raw, definition_raw in indexes:
                        index_name = _coerce_text(index_name_raw)
                        definition = _coerce_text(definition_raw)
                        db.add(DbIndex(table_id=table.id, name=index_name, definition=definition))

                    ctx.step = "samples"
                    ctx.context = "samples"
                    _checkpoint(db, ctx)

                    sample_rows = _fetch_samples(conn, ctx, table_schema, table_name, sample_limit)
                    if sample_rows:
                        db.add(Sample(table_id=table.id, rows=sample_rows))

            db.commit()


def _fetch_samples(conn, ctx: ScanContext, schema_name: str, table_name: str, sample_limit: int) -> list[dict[str, Any]]:
    ctx.step = "primary_keys"
    ctx.context = "primary_keys"
    ctx.schema_name = schema_name
    ctx.table_name = table_name

    pk_rows = _fetchall(
        conn,
        ctx,
        PRIMARY_KEY_QUERY,
        {"schema_name": schema_name, "table_name": table_name},
    )
    pk_columns = [_coerce_text(r[0]) for r in pk_rows]

    query_text = build_sample_query(schema_name, table_name, pk_columns)
    if not query_text:
        return []

    ctx.step = "sample_query"
    ctx.context = "sample_query"
    ctx.query = query_text
    ctx.params = {"limit": sample_limit}

    cols, fetched = _fetch_rows(conn, ctx, text(query_text), {"limit": sample_limit})

    out: list[dict[str, Any]] = []
    for row in fetched:
        out.append({c: _safe_obj(v) for c, v in zip(cols, row)})
    return out
