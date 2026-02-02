from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import httpx
from sqlalchemy import select, text
from sqlalchemy.engine import URL, create_engine
from sqlalchemy.orm import Session
from pydantic import BaseModel, ValidationError

from app.config import settings
from app.models import DbTable, DbColumn, DbConstraint, DbIndex, DbSchema, Scan, Connection
from app.security import EncryptionError, decrypt_secret

logger = logging.getLogger("atlasrag.sql_orchestrator")

FORBIDDEN_KEYWORDS = re.compile(
    r"\b(insert|update|delete|upsert|merge|drop|alter|create|grant|revoke|truncate|copy|execute|call)\b",
    re.IGNORECASE,
)
FORBIDDEN_FUNCTIONS = re.compile(
    r"\b(pg_read_file|pg_ls_dir|pg_sleep|dblink|lo_export|lo_import)\b",
    re.IGNORECASE,
)
FROM_JOIN_PATTERN = re.compile(
    r"\b(from|join)\s+([a-zA-Z0-9_\".]+)",
    re.IGNORECASE,
)


class PlannerQuery(BaseModel):
    name: str
    purpose: str
    sql: str
    expected_shape: dict[str, Any] | None = None
    safety: dict[str, Any] | None = None


class PlannerResponse(BaseModel):
    decision: str
    reason: str
    entities: list[str] = []
    queries: list[PlannerQuery] = []
    predefined_query_id: str | None = None
    clarifying_question: str | None = None


class ResponderUsedSQL(BaseModel):
    name: str
    sql: str
    rows_returned: int


class ResponderResponse(BaseModel):
    answer: str
    used_sql: list[ResponderUsedSQL] = []
    assumptions: list[str] = []
    caveats: list[str] = []
    followups: list[str] = []


@dataclass
class PredefinedQuery:
    id: str
    intent: str
    description: str
    dialect: str
    sql_template: str
    required_params: list[str]


def predefined_queries_catalog() -> list[PredefinedQuery]:
    return []


def _openai_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }


def _connection_info(connection: Connection) -> dict[str, Any]:
    try:
        password = decrypt_secret(connection.password_encrypted)
    except EncryptionError as exc:
        raise RuntimeError("Falha ao descriptografar a senha da conexão.") from exc
    return {
        "host": connection.host,
        "port": connection.port,
        "database": connection.database,
        "username": connection.username,
        "password": password,
        "ssl_mode": connection.ssl_mode,
    }


def _build_engine(info: dict[str, Any]):
    url = URL.create(
        "postgresql+psycopg2",
        username=info["username"],
        password=info["password"],
        host=info["host"],
        port=info["port"],
        database=info["database"],
        query={"sslmode": info["ssl_mode"]},
    )
    return create_engine(url, pool_pre_ping=True)


def _normalize_identifier(value: str) -> str:
    return value.strip().strip('"').lower()


def _extract_table_names(sql: str) -> set[str]:
    names = set()
    for _, raw in FROM_JOIN_PATTERN.findall(sql):
        cleaned = raw.strip().rstrip(",")
        cleaned = cleaned.split()[0]
        normalized = _normalize_identifier(cleaned)
        if normalized:
            names.add(normalized)
    return names


def _ensure_limit(sql: str, limit: int) -> str:
    if re.search(r"\blimit\s+\d+", sql, re.IGNORECASE):
        return sql
    return f"{sql.rstrip(';')} LIMIT {limit}"


def _validate_sql(sql: str, allowed_tables: set[str], max_rows: int) -> tuple[bool, str | None, str]:
    cleaned = sql.strip().rstrip(";")
    if ";" in cleaned:
        return False, "Múltiplas statements não são permitidas.", cleaned
    lowered = cleaned.lower()
    if not (lowered.startswith("select") or lowered.startswith("with")):
        return False, "Apenas SELECT/CTE são permitidos.", cleaned
    if FORBIDDEN_KEYWORDS.search(lowered):
        return False, "Comandos de escrita ou DDL não são permitidos.", cleaned
    if FORBIDDEN_FUNCTIONS.search(lowered):
        return False, "Funções perigosas não são permitidas.", cleaned
    referenced = _extract_table_names(cleaned)
    if referenced:
        missing = {name for name in referenced if name not in allowed_tables}
        if missing:
            return False, f"Tabelas fora do catálogo permitido: {sorted(missing)}", cleaned
    return True, None, _ensure_limit(cleaned, max_rows)


def _schema_context(db: Session, connection_ids: list[int]) -> tuple[dict[str, Any], set[str]]:
    if not connection_ids:
        return {"tables": [], "constraints": [], "indexes": []}, set()
    scans = (
        db.query(Scan)
        .filter(Scan.connection_id.in_(connection_ids), Scan.status == "completed")
        .order_by(Scan.connection_id, Scan.finished_at.desc().nullslast(), Scan.started_at.desc())
        .all()
    )
    latest_scan_ids: dict[int, int] = {}
    for scan in scans:
        if scan.connection_id not in latest_scan_ids:
            latest_scan_ids[scan.connection_id] = scan.id
    scan_ids = list(latest_scan_ids.values())
    if not scan_ids:
        return {"tables": [], "constraints": [], "indexes": []}, set()
    tables = (
        db.query(DbTable)
        .join(DbTable.schema)
        .filter(DbSchema.scan_id.in_(scan_ids))
        .order_by(DbTable.id)
        .all()
    )
    table_ids = [table.id for table in tables]
    columns = (
        db.query(DbColumn)
        .filter(DbColumn.table_id.in_(table_ids))
        .order_by(DbColumn.table_id, DbColumn.id)
        .all()
    )
    constraints = (
        db.query(DbConstraint)
        .filter(DbConstraint.table_id.in_(table_ids))
        .order_by(DbConstraint.table_id, DbConstraint.id)
        .all()
    )
    indexes = (
        db.query(DbIndex)
        .filter(DbIndex.table_id.in_(table_ids))
        .order_by(DbIndex.table_id, DbIndex.id)
        .all()
    )
    column_map: dict[int, list[dict[str, Any]]] = {}
    for column in columns:
        column_map.setdefault(column.table_id, []).append(
            {
                "name": column.name,
                "data_type": column.data_type,
                "is_nullable": column.is_nullable,
                "description": column.description,
                "annotations": column.annotations,
            }
        )
    allowed_tables: set[str] = set()
    for table in tables:
        schema_name = _normalize_identifier(table.schema.name)
        table_name = _normalize_identifier(table.name)
        if schema_name and table_name:
            allowed_tables.add(f"{schema_name}.{table_name}")
            allowed_tables.add(table_name)

    table_payload = []
    for table in tables[: settings.schema_context_tables_limit]:
        table_payload.append(
            {
                "schema": table.schema.name,
                "name": table.name,
                "table_type": table.table_type,
                "description": table.description,
                "annotations": table.annotations,
                "columns": (column_map.get(table.id, []))[: settings.schema_context_columns_limit],
            }
        )
    return {
        "tables": table_payload,
        "constraints": [
            {
                "table_id": constraint.table_id,
                "name": constraint.name,
                "type": constraint.constraint_type,
                "definition": constraint.definition,
            }
            for constraint in constraints[: settings.schema_context_constraints_limit]
        ],
        "indexes": [
            {"table_id": index.table_id, "name": index.name, "definition": index.definition}
            for index in indexes[: settings.schema_context_indexes_limit]
        ],
    }, allowed_tables


def _planner_prompt(payload: dict[str, Any]) -> list[dict[str, str]]:
    instructions = (
        "Você é o Planner SQL-RAG.\n"
        "Sua função é decidir se precisa consultar o banco e, se sim, propor 1..N SELECTs seguros e pequenos.\n"
        "Você DEVE responder somente com JSON válido conforme o schema do contrato."
    )
    return [
        {"role": "system", "content": instructions},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]


def _responder_prompt(payload: dict[str, Any]) -> list[dict[str, str]]:
    instructions = (
        "Você é o Responder SQL-RAG.\n"
        "Você deve responder ao usuário com base no schema_context e nos resultados retornados pelos SELECTs executados.\n"
        "Você DEVE responder somente com JSON válido conforme o contrato do Responder."
    )
    return [
        {"role": "system", "content": instructions},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]


def _call_llm(model: str, messages: list[dict[str, str]]) -> str:
    payload = {"model": model, "messages": messages, "temperature": 0.2}
    with httpx.Client(timeout=60) as client:
        response = client.post(
            "https://api.openai.com/v1/chat/completions",
            headers=_openai_headers(),
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
    return data["choices"][0]["message"]["content"]


def _parse_json_response(raw: str) -> dict[str, Any]:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("Resposta JSON inválida do LLM.") from exc


def _planner_request_payload(
    user_question: str,
    schema_context: dict[str, Any],
    predefined_queries: list[PredefinedQuery],
    db_dialect: str,
    conversation_context: list[dict[str, Any]],
    error: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "user_question": user_question,
        "schema_context": schema_context,
        "predefined_queries_catalog": [query.__dict__ for query in predefined_queries],
        "db_dialect": db_dialect,
        "constraints": {
            "max_queries": settings.sql_max_queries,
            "max_rows": settings.sql_max_rows,
            "timeout_ms": settings.sql_timeout_ms,
        },
        "conversation_context": conversation_context,
        "sql_error": error,
    }


def _responder_request_payload(
    user_question: str,
    schema_context: dict[str, Any],
    sql_results: list[dict[str, Any]],
    db_dialect: str,
) -> dict[str, Any]:
    return {
        "user_question": user_question,
        "schema_context": schema_context,
        "sql_results": sql_results,
        "db_dialect": db_dialect,
    }


def orchestrate_sql_rag(
    db: Session,
    user_question: str,
    connection_ids: list[int],
    conversation_context: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required")

    request_id = str(uuid4())
    schema_context, allowed_tables = _schema_context(db, connection_ids)
    predefined = predefined_queries_catalog()
    error_payload: dict[str, Any] | None = None
    sql_results: list[dict[str, Any]] = []
    used_sql: list[dict[str, Any]] = []

    for attempt in range(settings.planner_retry_limit + 1):
        planner_payload = _planner_request_payload(
            user_question,
            schema_context,
            predefined,
            settings.db_dialect,
            conversation_context,
            error_payload,
        )
        planner_raw = _call_llm(settings.planner_model, _planner_prompt(planner_payload))
        try:
            planner_data = _parse_json_response(planner_raw)
            planner_response = PlannerResponse.model_validate(planner_data)
        except (ValueError, ValidationError) as exc:
            logger.warning(
                "planner_invalid_response",
                extra={"request_id": request_id, "error": str(exc), "response": planner_raw[:2000]},
            )
            planner_response = PlannerResponse(
                decision="need_clarification",
                reason="Planner retornou JSON inválido.",
                clarifying_question="Pode reformular sua pergunta com mais detalhes?",
            )

        logger.info(
            "planner_decision",
            extra={
                "request_id": request_id,
                "decision": planner_response.decision,
                "reason": planner_response.reason,
                "query_count": len(planner_response.queries),
            },
        )

        if planner_response.decision == "no_sql_needed":
            responder_payload = _responder_request_payload(
                user_question, schema_context, sql_results, settings.db_dialect
            )
            responder_raw = _call_llm(settings.responder_model, _responder_prompt(responder_payload))
            try:
                responder_data = _parse_json_response(responder_raw)
                responder = ResponderResponse.model_validate(responder_data)
            except (ValueError, ValidationError) as exc:
                logger.warning(
                    "responder_invalid_response",
                    extra={"request_id": request_id, "error": str(exc), "response": responder_raw[:2000]},
                )
                return "Não foi possível formatar a resposta final. Pode tentar novamente?", []
            return responder.answer, [item.model_dump() for item in responder.used_sql]

        if planner_response.decision == "need_clarification":
            return planner_response.clarifying_question or "Pode fornecer mais detalhes?", []

        if planner_response.decision == "refuse":
            return planner_response.reason, []

        queries_to_run: list[PlannerQuery] = []
        if planner_response.decision == "use_predefined" and planner_response.predefined_query_id:
            match = next(
                (query for query in predefined if query.id == planner_response.predefined_query_id),
                None,
            )
            if match:
                queries_to_run = [
                    PlannerQuery(
                        name=match.intent,
                        purpose=match.description,
                        sql=match.sql_template,
                    )
                ]
        if planner_response.decision == "run_selects":
            queries_to_run = planner_response.queries[: settings.sql_max_queries]

        if not queries_to_run:
            return "Não foi possível identificar uma consulta segura para executar.", []

        sql_results = []
        error_payload = None
        start = time.monotonic()
        for query in queries_to_run:
            ok, error, safe_sql = _validate_sql(query.sql, allowed_tables, settings.sql_max_rows)
            if not ok:
                error_payload = {
                    "sql_error": {
                        "query_name": query.name,
                        "message": error or "Consulta inválida.",
                    }
                }
                break
            connection_id = connection_ids[0] if connection_ids else None
            if not connection_id:
                error_payload = {
                    "sql_error": {
                        "query_name": query.name,
                        "message": "Nenhuma conexão disponível para executar a consulta.",
                    }
                }
                break
            connection = db.get(Connection, connection_id)
            if not connection:
                error_payload = {
                    "sql_error": {
                        "query_name": query.name,
                        "message": "Conexão não encontrada.",
                    }
                }
                break
            info = _connection_info(connection)
            engine = _build_engine(info)
            rows: list[dict[str, Any]] = []
            columns: list[str] = []
            error_message = None
            try:
                with engine.connect() as conn:
                    if settings.db_dialect == "postgres":
                        conn.execute(text("SET statement_timeout = :timeout"), {"timeout": settings.sql_timeout_ms})
                    result = conn.execute(text(safe_sql))
                    rows = [dict(row) for row in result.mappings().fetchmany(settings.sql_max_rows)]
                    columns = list(result.keys())
            except Exception as exc:
                error_message = str(exc)

            if error_message:
                error_payload = {
                    "sql_error": {
                        "query_name": query.name,
                        "message": error_message,
                    }
                }
                break
            sql_results.append(
                {
                    "name": query.name,
                    "sql": safe_sql,
                    "columns": columns,
                    "rows": rows,
                    "row_count": len(rows),
                    "truncated": len(rows) >= settings.sql_max_rows,
                }
            )
            used_sql.append({"name": query.name, "sql": safe_sql, "rows_returned": len(rows)})

        elapsed_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "sql_execution_completed",
            extra={
                "request_id": request_id,
                "queries": len(queries_to_run),
                "rows_returned": sum(item.get("row_count", 0) for item in sql_results),
                "elapsed_ms": elapsed_ms,
            },
        )

        if error_payload:
            if attempt < settings.planner_retry_limit:
                continue
            return "Não foi possível executar as consultas solicitadas. Pode ajustar a pergunta?", []

        responder_payload = _responder_request_payload(
            user_question, schema_context, sql_results, settings.db_dialect
        )
        responder_raw = _call_llm(settings.responder_model, _responder_prompt(responder_payload))
        try:
            responder_data = _parse_json_response(responder_raw)
            responder = ResponderResponse.model_validate(responder_data)
        except (ValueError, ValidationError) as exc:
            logger.warning(
                "responder_invalid_response",
                extra={"request_id": request_id, "error": str(exc), "response": responder_raw[:2000]},
            )
            return "Não foi possível formatar a resposta final. Pode tentar novamente?", []
        return responder.answer, [item.model_dump() for item in responder.used_sql]

    return "Não foi possível concluir a resposta.", []
