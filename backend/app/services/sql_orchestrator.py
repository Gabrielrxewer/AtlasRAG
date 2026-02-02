from __future__ import annotations

import json
import logging
import re
import time
from datetime import date, datetime, timezone
from decimal import Decimal
from dataclasses import dataclass
from typing import Any, Literal
from uuid import uuid4

import httpx
from sqlalchemy import text
from sqlalchemy.engine import URL, create_engine, Engine
from sqlalchemy.orm import Session
from pydantic import BaseModel, ValidationError

from app.config import settings
from app.models import DbTable, DbColumn, DbConstraint, DbIndex, DbSchema, Scan, Connection
from app.security import EncryptionError, decrypt_secret
from app.services.scan import reconcile_scan_status

logger = logging.getLogger("atlasrag.sql_orchestrator")

FORBIDDEN_KEYWORDS = re.compile(
    r"\b(insert|update|delete|upsert|merge|drop|alter|create|grant|revoke|truncate|copy|execute|call)\b",
    re.IGNORECASE,
)
FORBIDDEN_FUNCTIONS = re.compile(
    r"\b(pg_read_file|pg_ls_dir|pg_sleep|dblink|lo_export|lo_import)\b",
    re.IGNORECASE,
)
SELECT_INTO_PATTERN = re.compile(
    r"\bselect\b[\s\S]+?\binto\b",
    re.IGNORECASE,
)
FOR_UPDATE_PATTERN = re.compile(
    r"\bfor\s+(update|share)\b",
    re.IGNORECASE,
)
FROM_JOIN_PATTERN = re.compile(
    r"\b(from|join)\s+([a-zA-Z0-9_\".]+)",
    re.IGNORECASE,
)
CTE_NAME_PATTERN = re.compile(
    r"\bwith\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+as\s*\(",
    re.IGNORECASE,
)
FOLLOWING_CTE_PATTERN = re.compile(
    r"\)\s*,\s*([a-zA-Z_][a-zA-Z0-9_]*)\s+as\s*\(",
    re.IGNORECASE,
)

ENGINE_CACHE: dict[tuple[int, str | None], Engine] = {}
ENGINE_CACHE_ORDER: list[tuple[int, str | None]] = []


class PlannerQuery(BaseModel):
    name: str
    purpose: str
    sql: str
    connection_id: int | None = None
    expected_shape: dict[str, Any] | None = None
    safety: dict[str, Any] | None = None


class PlannerResponse(BaseModel):
    decision: Literal[
        "run_selects",
        "use_predefined",
        "no_sql_needed",
        "need_clarification",
        "refuse",
    ]
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


class ExecutedQuery(BaseModel):
    name: str
    sql: str
    rows_returned: int
    truncated: bool
    elapsed_ms: int
    connection_id: int


def predefined_queries_catalog() -> list[PredefinedQuery]:
    return []


INTENT_LIST_PATTERN = re.compile(
    r"\b(listar|liste|listar|mostrar|mostre|citar|cite|exemplos?|registros?)\b",
    re.IGNORECASE,
)
INTENT_TOP_PATTERN = re.compile(
    r"\b(maior|menor|top|últim[oa]|ultimo|primeiro|mais caro|mais barata|mais alto|mais baixo)\b",
    re.IGNORECASE,
)
LIST_LIMIT_PATTERN = re.compile(r"\b(?:cite|listar|liste|mostre|mostrar)\s+(\d+)\b", re.IGNORECASE)
NUMERIC_COLUMN_CANDIDATES = [
    "value",
    "valor",
    "price",
    "preco",
    "amount",
    "total",
    "cost",
    "volume",
    "market_cap",
    "marketcap",
]
LIST_ORDER_CANDIDATES = ["id", "created_at", "updated_at", "timestamp", "date", "data"]


def _normalize_question(question: str) -> str:
    return re.sub(r"[^\w\s]", " ", question).lower()


def _flatten_schema_tables(schema_context: dict[str, Any]) -> list[dict[str, Any]]:
    tables: list[dict[str, Any]] = []
    for connection in schema_context.get("connections", []):
        connection_id = connection.get("connection_id")
        for table in connection.get("tables", []) or []:
            tables.append(
                {
                    "connection_id": connection_id,
                    "schema": table.get("schema"),
                    "name": table.get("name"),
                    "columns": table.get("columns") or [],
                }
            )
    return tables


def _match_table_candidates(question: str, tables: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = _normalize_question(question)
    exact_matches = []
    fuzzy_matches = []
    for table in tables:
        name = (table.get("name") or "").lower()
        if not name:
            continue
        if re.search(rf"\b{name}\b", normalized):
            exact_matches.append(table)
        elif name in normalized:
            fuzzy_matches.append(table)
    return exact_matches or fuzzy_matches


def _select_columns(table: dict[str, Any]) -> list[str]:
    columns = [col.get("name") for col in table.get("columns", []) if col.get("name")]
    preferred = []
    for candidate in ["id", "name", "symbol", "ticker", "price", "value", "created_at"]:
        if candidate in columns:
            preferred.append(candidate)
    if preferred:
        return preferred[:4]
    return columns[:4] if columns else ["*"]


def _pick_numeric_column(table: dict[str, Any]) -> str | None:
    columns = [col.get("name") for col in table.get("columns", []) if col.get("name")]
    for candidate in NUMERIC_COLUMN_CANDIDATES:
        if candidate in columns:
            return candidate
    return columns[0] if columns else None


def _pick_order_column(table: dict[str, Any]) -> str | None:
    columns = [col.get("name") for col in table.get("columns", []) if col.get("name")]
    for candidate in LIST_ORDER_CANDIDATES:
        if candidate in columns:
            return candidate
    return columns[0] if columns else None


def fallback_plan(
    user_question: str,
    schema_context: dict[str, Any],
    connection_ids: list[int],
    max_rows: int,
) -> PlannerResponse:
    tables = _flatten_schema_tables(schema_context)
    candidates = _match_table_candidates(user_question, tables)
    if not candidates and len(tables) == 1:
        candidates = tables
    if not candidates:
        return PlannerResponse(
            decision="need_clarification",
            reason="Nenhuma tabela candidata encontrada para responder.",
            clarifying_question="Qual tabela devo usar para responder?",
        )
    if len(candidates) > 1:
        names = ", ".join(sorted({candidate.get("name", "") for candidate in candidates if candidate.get("name")}))
        return PlannerResponse(
            decision="need_clarification",
            reason="Existem múltiplas tabelas candidatas.",
            clarifying_question=f"Qual tabela devo usar: {names}?",
        )
    table = candidates[0]
    connection_id = table.get("connection_id") or (connection_ids[0] if connection_ids else None)
    schema_name = table.get("schema")
    table_name = table.get("name")
    if not connection_id or not table_name:
        return PlannerResponse(
            decision="need_clarification",
            reason="Tabela ou conexão não resolvida.",
            clarifying_question="Qual conexão devo usar para responder?",
        )
    full_table = f"{schema_name}.{table_name}" if schema_name else table_name
    normalized_question = _normalize_question(user_question)
    limit_match = LIST_LIMIT_PATTERN.search(normalized_question)
    limit = min(int(limit_match.group(1)), max_rows) if limit_match else min(5, max_rows)
    columns = _select_columns(table)
    order_col = _pick_order_column(table)
    if INTENT_TOP_PATTERN.search(normalized_question):
        numeric_column = _pick_numeric_column(table)
        if not numeric_column:
            numeric_column = columns[0] if columns else "*"
        direction = "ASC" if "menor" in normalized_question else "DESC"
        sql = f"SELECT {', '.join(columns)} FROM {full_table} ORDER BY {numeric_column} {direction} LIMIT 1"
        return PlannerResponse(
            decision="run_selects",
            reason="Fallback heurístico para maior/menor/top.",
            queries=[
                PlannerQuery(
                    name="fallback_top",
                    purpose="Identificar valor extremo solicitado.",
                    sql=sql,
                    connection_id=connection_id,
                )
            ],
        )
    if INTENT_LIST_PATTERN.search(normalized_question):
        order_clause = f" ORDER BY {order_col} DESC" if order_col else ""
        sql = f"SELECT {', '.join(columns)} FROM {full_table}{order_clause} LIMIT {limit}"
        return PlannerResponse(
            decision="run_selects",
            reason="Fallback heurístico para listar registros.",
            queries=[
                PlannerQuery(
                    name="fallback_list",
                    purpose="Listar registros solicitados.",
                    sql=sql,
                    connection_id=connection_id,
                )
            ],
        )
    return PlannerResponse(
        decision="no_sql_needed",
        reason="Pergunta não exige SELECT explícito.",
    )


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


def _build_engine(connection_id: int, info: dict[str, Any], cache_key: str | None) -> Engine:
    key = (connection_id, cache_key)
    if key in ENGINE_CACHE:
        return ENGINE_CACHE[key]
    url = URL.create(
        "postgresql+psycopg2",
        username=info["username"],
        password=info["password"],
        host=info["host"],
        port=info["port"],
        database=info["database"],
        query={"sslmode": info["ssl_mode"]},
    )
    engine = create_engine(url, pool_pre_ping=True)
    ENGINE_CACHE[key] = engine
    ENGINE_CACHE_ORDER.append(key)
    while len(ENGINE_CACHE_ORDER) > settings.sql_engine_cache_size:
        evicted = ENGINE_CACHE_ORDER.pop(0)
        ENGINE_CACHE.pop(evicted, None)
    return engine


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


def _extract_cte_names(sql: str) -> set[str]:
    names = {match.group(1).lower() for match in CTE_NAME_PATTERN.finditer(sql)}
    for match in FOLLOWING_CTE_PATTERN.finditer(sql):
        names.add(match.group(1).lower())
    return names


def _ensure_limit(sql: str, limit: int) -> str:
    match = re.search(r"\blimit\s+(\d+|:[a-zA-Z_][a-zA-Z0-9_]*|all)\b", sql, re.IGNORECASE)
    if match:
        raw_value = match.group(1)
        if raw_value.isdigit():
            existing = int(raw_value)
            if existing <= limit:
                return sql
        return re.sub(r"\blimit\s+(\d+|:[a-zA-Z_][a-zA-Z0-9_]*|all)\b", f"LIMIT {limit}", sql, flags=re.IGNORECASE)
    return f"{sql.rstrip(';')} LIMIT {limit}"


def _validate_sql(sql: str, allowed_tables: set[str], max_rows: int) -> tuple[bool, str | None, str]:
    cleaned = sql.strip().rstrip(";")
    if ";" in cleaned:
        return False, "Múltiplas statements não são permitidas.", cleaned
    lowered = cleaned.lower()
    if not (lowered.startswith("select") or lowered.startswith("with")):
        return False, "Apenas SELECT/CTE são permitidos.", cleaned
    if SELECT_INTO_PATTERN.search(lowered):
        return False, "SELECT INTO não é permitido.", cleaned
    if FOR_UPDATE_PATTERN.search(lowered):
        return False, "SELECT com FOR UPDATE/SHARE não é permitido.", cleaned
    if FORBIDDEN_KEYWORDS.search(lowered):
        return False, "Comandos de escrita ou DDL não são permitidos.", cleaned
    if FORBIDDEN_FUNCTIONS.search(lowered):
        return False, "Funções perigosas não são permitidas.", cleaned
    referenced = _extract_table_names(cleaned)
    cte_names = _extract_cte_names(cleaned)
    referenced = {name for name in referenced if name not in cte_names}
    if referenced:
        missing = {name for name in referenced if name not in allowed_tables}
        if missing:
            if "with" in lowered:
                missing_qualified = {name for name in missing if "." in name}
                if missing_qualified:
                    return False, f"Tabelas fora do catálogo permitido: {sorted(missing_qualified)}", cleaned
            else:
                return False, f"Tabelas fora do catálogo permitido: {sorted(missing)}", cleaned
    return True, None, _ensure_limit(cleaned, max_rows)


def _scan_has_catalog(db: Session, scan_id: int) -> bool:
    result = db.execute(
        text(
            """
            SELECT COUNT(*)
            FROM db_tables t
            JOIN db_schemas s ON s.id = t.schema_id
            WHERE s.scan_id = :scan_id
            """
        ),
        {"scan_id": scan_id},
    ).scalar_one()
    return int(result or 0) > 0


def _select_latest_scan_ids(
    db: Session, scans: list[Scan]
) -> tuple[dict[int, int], set[int]]:
    latest_scan_ids: dict[int, int] = {}
    running_scan_ids: set[int] = set()
    scans_by_connection: dict[int, list[Scan]] = {}
    for scan in scans:
        scans_by_connection.setdefault(scan.connection_id, []).append(scan)
    for connection_id, items in scans_by_connection.items():
        completed = next((scan for scan in items if scan.status == "completed"), None)
        if completed:
            latest_scan_ids[connection_id] = completed.id
            continue
        running = next(
            (scan for scan in items if scan.status == "running" and _scan_has_catalog(db, scan.id)),
            None,
        )
        if running:
            latest_scan_ids[connection_id] = running.id
            running_scan_ids.add(running.id)
    return latest_scan_ids, running_scan_ids


def _schema_context(
    db: Session, connection_ids: list[int]
) -> tuple[dict[str, Any], dict[int, set[str]]]:
    if not connection_ids:
        return {"connections": []}, {}
    scans = (
        db.query(Scan)
        .filter(Scan.connection_id.in_(connection_ids), Scan.status.in_(["completed", "running"]))
        .order_by(Scan.connection_id, Scan.finished_at.desc().nullslast(), Scan.started_at.desc())
        .all()
    )
    latest_scan_ids, running_scan_ids = _select_latest_scan_ids(db, scans)
    if running_scan_ids:
        for scan in scans:
            if scan.id in running_scan_ids:
                scan.status = "completed"
                scan.finished_at = scan.finished_at or datetime.now(timezone.utc)
                scan.error_message = None
                logger.warning(
                    "scan_status_auto_corrected",
                    extra={"scan_id": scan.id, "connection_id": scan.connection_id},
                )
        db.commit()
    scan_ids = list(latest_scan_ids.values())
    if not scan_ids:
        return {"connections": []}, {}
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
    table_name_map: dict[int, dict[str, str | int]] = {}
    allowed_tables_by_connection: dict[int, set[str]] = {}
    for table in tables:
        connection_id = table.schema.scan.connection_id if table.schema and table.schema.scan else None
        table_name_map[table.id] = {
            "schema": table.schema.name,
            "name": table.name,
            "connection_id": connection_id,
        }
        if connection_id is None:
            continue
        schema_name = _normalize_identifier(table.schema.name)
        table_name = _normalize_identifier(table.name)
        if schema_name and table_name:
            allowed_tables_by_connection.setdefault(connection_id, set()).update(
                {f"{schema_name}.{table_name}", table_name}
            )

    tables_by_connection: dict[int, list[dict[str, Any]]] = {}
    for table in tables:
        connection_id = table.schema.scan.connection_id if table.schema and table.schema.scan else None
        if connection_id is None:
            continue
        if len(tables_by_connection.get(connection_id, [])) >= settings.schema_context_tables_limit:
            continue
        sample_rows = []
        if table.samples:
            sample_rows = (table.samples[0].rows or [])[: settings.schema_context_sample_rows_limit]
        tables_by_connection.setdefault(connection_id, []).append(
            {
                "schema": table.schema.name,
                "name": table.name,
                "table_type": table.table_type,
                "description": table.description,
                "annotations": table.annotations,
                "columns": (column_map.get(table.id, []))[: settings.schema_context_columns_limit],
                "sample_rows": sample_rows,
            }
        )

    connections_payload = []
    for connection_id in connection_ids:
        connections_payload.append(
            {
                "connection_id": connection_id,
                "tables": tables_by_connection.get(connection_id, []),
                "constraints": [
                    {
                        "schema": table_name_map.get(constraint.table_id, {}).get("schema"),
                        "table": table_name_map.get(constraint.table_id, {}).get("name"),
                        "name": constraint.name,
                        "type": constraint.constraint_type,
                        "definition": constraint.definition,
                    }
                    for constraint in constraints
                    if table_name_map.get(constraint.table_id, {}).get("connection_id") == connection_id
                ][: settings.schema_context_constraints_limit],
                "indexes": [
                    {
                        "schema": table_name_map.get(index.table_id, {}).get("schema"),
                        "table": table_name_map.get(index.table_id, {}).get("name"),
                        "name": index.name,
                        "definition": index.definition,
                    }
                    for index in indexes
                    if table_name_map.get(index.table_id, {}).get("connection_id") == connection_id
                ][: settings.schema_context_indexes_limit],
            }
        )
    return {"connections": connections_payload}, allowed_tables_by_connection


def _planner_prompt(payload: dict[str, Any]) -> list[dict[str, str]]:
    error_context = payload.get("error_context") or {}
    has_planner_error = bool(error_context.get("planner_error"))
    instructions = (
        "Você é o Planner SQL-RAG.\n"
        "Sua função é decidir se precisa consultar o banco e, se sim, propor 1..N SELECTs seguros e pequenos.\n"
        "Você DEVE responder somente com JSON válido conforme o schema do contrato.\n"
        "Regras:\n"
        "- Nunca responda em texto livre. Responda somente JSON.\n"
        "- Se houver error_context, corrija as queries propostas e corrija o formato.\n"
        "- Use need_clarification apenas quando faltar informação essencial (ex.: nenhuma tabela candidata ou ambiguidade real).\n"
        "- Se o usuário pedir exemplos/registros/listar/citar/mostrar N itens e houver tabela alvo clara, use decision=run_selects.\n"
        "- Ao listar exemplos, inclua ORDER BY (id DESC ou created_at DESC) quando existirem essas colunas.\n"
        "- Sempre respeite constraints.max_rows e use LIMIT conforme solicitado (<= max_rows).\n"
        "- Se houver múltiplas conexões, preencha connection_id em cada query.\n"
        "\n"
        f"{'IMPORTANTE: você respondeu inválido antes. Responda JSON estrito agora.' if has_planner_error else ''}\n"
        "JSON schema esperado:\n"
        "{\n"
        '  "decision": "run_selects" | "use_predefined" | "no_sql_needed" | "need_clarification" | "refuse",\n'
        '  "reason": "string",\n'
        '  "entities": ["string"],\n'
        '  "queries": [\n'
        "    {\n"
        '      "name": "string",\n'
        '      "purpose": "string",\n'
        '      "sql": "string",\n'
        '      "connection_id": 0,\n'
        '      "expected_shape": {"columns": ["string"], "notes": "string"},\n'
        '      "safety": {"limit": 5, "reason": "string"}\n'
        "    }\n"
        "  ],\n"
        '  "predefined_query_id": "string | null",\n'
        '  "clarifying_question": "string | null"\n'
        "}\n"
        "\n"
        "Exemplos:\n"
        "1) run_selects\n"
        "{\n"
        '  "decision": "run_selects",\n'
        '  "reason": "Usuário pediu listar 5 assets e há tabela assets no catálogo.",\n'
        '  "entities": ["assets"],\n'
        '  "queries": [\n'
        "    {\n"
        '      "name": "listar_assets",\n'
        '      "purpose": "Listar 5 assets com campos básicos.",\n'
        '      "sql": "SELECT id, name FROM public.assets ORDER BY id DESC LIMIT 5",\n'
        '      "connection_id": 1,\n'
        '      "expected_shape": {"columns": ["id", "name"], "notes": "5 linhas"},\n'
        '      "safety": {"limit": 5, "reason": "Pedido explícito do usuário"}\n'
        "    }\n"
        "  ],\n"
        '  "predefined_query_id": null,\n'
        '  "clarifying_question": null\n'
        "}\n"
        "2) use_predefined\n"
        "{\n"
        '  "decision": "use_predefined",\n'
        '  "reason": "Há query pré-definida compatível.",\n'
        '  "entities": ["orders"],\n'
        '  "queries": [],\n'
        '  "predefined_query_id": "orders_last_30_days",\n'
        '  "clarifying_question": null\n'
        "}\n"
        "3) no_sql_needed\n"
        "{\n"
        '  "decision": "no_sql_needed",\n'
        '  "reason": "A pergunta é conceitual e pode ser respondida sem dados.",\n'
        '  "entities": [],\n'
        '  "queries": [],\n'
        '  "predefined_query_id": null,\n'
        '  "clarifying_question": null\n'
        "}\n"
        "4) need_clarification\n"
        "{\n"
        '  "decision": "need_clarification",\n'
        '  "reason": "Existem múltiplas tabelas de assets e falta contexto.",\n'
        '  "entities": ["assets"],\n'
        '  "queries": [],\n'
        '  "predefined_query_id": null,\n'
        '  "clarifying_question": "Qual tabela de assets devo usar: assets_core ou assets_legacy?"\n'
        "}\n"
        "5) refuse\n"
        "{\n"
        '  "decision": "refuse",\n'
        '  "reason": "A solicitação viola políticas de acesso.",\n'
        '  "entities": [],\n'
        '  "queries": [],\n'
        '  "predefined_query_id": null,\n'
        '  "clarifying_question": null\n'
        "}\n"
    )
    return [
        {"role": "system", "content": instructions},
        {"role": "user", "content": _json_dumps_safe(payload)},
    ]


def _responder_prompt(payload: dict[str, Any], agent_system_prompt: str) -> list[dict[str, str]]:
    instructions = (
        "Você é o Responder SQL-RAG.\n"
        "Você deve responder ao usuário com base no schema_context e nos resultados retornados pelos SELECTs executados.\n"
        "Você DEVE responder somente com JSON válido conforme o contrato do Responder.\n"
        "\n"
        "JSON schema esperado:\n"
        "{\n"
        '  "answer": "string",\n'
        '  "used_sql": [\n'
        "    {\n"
        '      "name": "string",\n'
        '      "sql": "string",\n'
        '      "rows_returned": 0\n'
        "    }\n"
        "  ],\n"
        '  "assumptions": ["string"],\n'
        '  "caveats": ["string"],\n'
        '  "followups": ["string"]\n'
        "}\n"
        "\n"
        "Exemplo:\n"
        "{\n"
        '  "answer": "Encontrei 5 assets: Asset A, Asset B, Asset C, Asset D e Asset E.",\n'
        '  "used_sql": [{"name": "listar_assets", "sql": "SELECT id, name FROM public.assets LIMIT 5", "rows_returned": 5}],\n'
        '  "assumptions": [],\n'
        '  "caveats": ["Os resultados podem estar truncados ao limite solicitado."],\n'
        '  "followups": ["Quer filtrar por status ou data?"]\n'
        "}\n"
    )
    return [
        {"role": "system", "content": f"{agent_system_prompt}\n\n{instructions}"},
        {"role": "user", "content": _json_dumps_safe(payload)},
    ]


def _call_llm(
    model: str, messages: list[dict[str, str]], response_format: dict[str, Any] | None = None
) -> str:
    payload: dict[str, Any] = {"model": model, "messages": messages, "temperature": 0.2}
    if response_format and "Planner SQL-RAG" in (messages[0].get("content") or ""):
        payload["temperature"] = 0
    if response_format:
        payload["response_format"] = response_format
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
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.replace("json", "", 1).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError("Resposta JSON inválida do LLM.") from exc


def _json_default(value: Any) -> str:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _json_dumps_safe(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, default=_json_default)


def _planner_request_payload(
    user_question: str,
    schema_context: dict[str, Any],
    predefined_queries: list[PredefinedQuery],
    db_dialect: str,
    conversation_context: list[dict[str, Any]],
    error: dict[str, Any] | None,
    connection_ids: list[int],
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
        "error_context": error,
        "available_connection_ids": connection_ids,
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
    agent_system_prompt: str,
) -> tuple[str, list[dict[str, Any]], str]:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required")
    if settings.db_dialect != "postgres":
        logger.warning(
            "sql_orchestrator_unsupported_dialect",
            extra={"db_dialect": settings.db_dialect},
        )
        return "Dialeto de banco ainda não suportado para execução segura.", [], ""

    request_id = str(uuid4())
    reconcile_scan_status(db, connection_ids)
    schema_context, allowed_tables_by_connection = _schema_context(db, connection_ids)
    connections_payload = schema_context.get("connections", [])
    has_any_table = any(connection.get("tables") for connection in connections_payload)
    if not has_any_table:
        return "Não há catálogo/scan concluído. Execute o scan/reindexação do catálogo.", [], ""
    predefined = predefined_queries_catalog()
    error_payload: dict[str, Any] | None = None
    sql_results: list[dict[str, Any]] = []
    executed_queries: list[ExecutedQuery] = []
    tool_payload = ""

    for attempt in range(settings.planner_retry_limit + 1):
        if attempt == 0:
            error_payload = None
        sql_results = []
        executed_queries = []
        previous_sql_summary: list[dict[str, Any]] = []
        retry_attempt = False
        for round_index in range(settings.agent_select_rounds):
            planner_payload = _planner_request_payload(
                user_question,
                schema_context,
                predefined,
                settings.db_dialect,
                conversation_context,
                error_payload,
                connection_ids,
            )
            if previous_sql_summary:
                planner_payload["previous_sql_results_summary"] = previous_sql_summary
            try:
                planner_raw = _call_llm(
                    settings.planner_model,
                    _planner_prompt(planner_payload),
                    response_format={"type": "json_object"},
                )
            except httpx.HTTPStatusError:
                planner_raw = _call_llm(
                    settings.planner_model,
                    _planner_prompt(planner_payload),
                    response_format=None,
                )
            planner_invalid = False
            try:
                planner_data = _parse_json_response(planner_raw)
                planner_response = PlannerResponse.model_validate(planner_data)
            except (ValueError, ValidationError) as exc:
                logger.warning(
                    "planner_invalid_response",
                    extra={"request_id": request_id, "error": str(exc), "response": planner_raw[:2000]},
                )
                error_payload = {
                    "planner_error": {
                        "message": "Planner retornou JSON inválido.",
                        "raw_preview": planner_raw[:500],
                    }
                }
                planner_invalid = True

            if planner_invalid:
                if INTENT_LIST_PATTERN.search(user_question) or INTENT_TOP_PATTERN.search(user_question):
                    planner_response = fallback_plan(
                        user_question, schema_context, connection_ids, settings.sql_max_rows
                    )
                else:
                    retry_attempt = True
                    break

            logger.info(
                "planner_decision",
                extra={
                    "request_id": request_id,
                    "decision": planner_response.decision,
                    "reason": planner_response.reason,
                    "query_count": len(planner_response.queries),
                    "round": round_index + 1,
                },
            )

            if planner_response.decision == "no_sql_needed":
                responder_payload = _responder_request_payload(
                    user_question, schema_context, sql_results, settings.db_dialect
                )
                try:
                    responder_raw = _call_llm(
                        settings.responder_model,
                        _responder_prompt(responder_payload, agent_system_prompt),
                        response_format={"type": "json_object"},
                    )
                except httpx.HTTPStatusError:
                    responder_raw = _call_llm(
                        settings.responder_model,
                        _responder_prompt(responder_payload, agent_system_prompt),
                        response_format=None,
                    )
                try:
                    responder_data = _parse_json_response(responder_raw)
                    responder = ResponderResponse.model_validate(responder_data)
                except (ValueError, ValidationError) as exc:
                    logger.warning(
                        "responder_invalid_response",
                        extra={"request_id": request_id, "error": str(exc), "response": responder_raw[:2000]},
                    )
                    return "Não foi possível formatar a resposta final. Pode tentar novamente?", [], ""
                return responder.answer, [item.model_dump() for item in executed_queries], ""

            if planner_response.decision == "need_clarification":
                if INTENT_LIST_PATTERN.search(user_question) or INTENT_TOP_PATTERN.search(user_question):
                    planner_response = fallback_plan(
                        user_question, schema_context, connection_ids, settings.sql_max_rows
                    )
                    if planner_response.decision == "need_clarification":
                        return planner_response.clarifying_question or "Pode fornecer mais detalhes?", [], ""
                else:
                    return planner_response.clarifying_question or "Pode fornecer mais detalhes?", [], ""

            if planner_response.decision == "refuse":
                return planner_response.reason, [], ""

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
                return "Não foi possível identificar uma consulta segura para executar.", [], ""

            error_payload = None
            start = time.monotonic()
            for query in queries_to_run:
                connection_id = query.connection_id or (connection_ids[0] if connection_ids else None)
                if connection_id and connection_id not in connection_ids:
                    error_payload = {
                        "sql_error": {
                            "query_name": query.name,
                            "message": "Conexão não permitida para esta consulta.",
                        }
                    }
                    break
                if not connection_id:
                    error_payload = {
                        "sql_error": {
                            "query_name": query.name,
                            "message": "Nenhuma conexão disponível para executar a consulta.",
                        }
                    }
                    break
                allowed_tables = allowed_tables_by_connection.get(connection_id, set())
                ok, error, safe_sql = _validate_sql(query.sql, allowed_tables, settings.sql_max_rows)
                if not ok:
                    error_payload = {
                        "sql_error": {
                            "query_name": query.name,
                            "message": error or "Consulta inválida.",
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
                cache_key = connection.updated_at.isoformat() if connection.updated_at else None
                engine = _build_engine(connection_id, info, cache_key)
                rows: list[dict[str, Any]] = []
                columns: list[str] = []
                error_message = None
                query_start = time.monotonic()
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
                        "connection_id": connection_id,
                    }
                )
                executed_queries.append(
                    ExecutedQuery(
                        name=query.name,
                        sql=safe_sql,
                        rows_returned=len(rows),
                        truncated=len(rows) >= settings.sql_max_rows,
                        elapsed_ms=int((time.monotonic() - query_start) * 1000),
                        connection_id=connection_id,
                    )
                )

            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.info(
                "sql_execution_completed",
                extra={
                    "request_id": request_id,
                    "queries": len(queries_to_run),
                    "rows_returned": sum(item.get("row_count", 0) for item in sql_results),
                    "elapsed_ms": elapsed_ms,
                    "round": round_index + 1,
                },
            )

            if error_payload:
                if attempt < settings.planner_retry_limit:
                    break
                return "Não foi possível executar as consultas solicitadas. Pode ajustar a pergunta?", [], ""

            previous_sql_summary = [
                {
                    "name": item["name"],
                    "sql": item["sql"],
                    "row_count": item["row_count"],
                    "truncated": item["truncated"],
                    "connection_id": item["connection_id"],
                    "round": round_index + 1,
                }
                for item in sql_results
            ]

            if round_index < settings.agent_select_rounds - 1:
                continue

            responder_payload = _responder_request_payload(
                user_question, schema_context, sql_results, settings.db_dialect
            )
            try:
                responder_raw = _call_llm(
                    settings.responder_model,
                    _responder_prompt(responder_payload, agent_system_prompt),
                    response_format={"type": "json_object"},
                )
            except httpx.HTTPStatusError:
                responder_raw = _call_llm(
                    settings.responder_model,
                    _responder_prompt(responder_payload, agent_system_prompt),
                    response_format=None,
                )
            try:
                responder_data = _parse_json_response(responder_raw)
                responder = ResponderResponse.model_validate(responder_data)
            except (ValueError, ValidationError) as exc:
                logger.warning(
                    "responder_invalid_response",
                    extra={"request_id": request_id, "error": str(exc), "response": responder_raw[:2000]},
                )
                return "Não foi possível formatar a resposta final. Pode tentar novamente?", [], ""
            tool_payload = json.dumps(
                {
                    "request_id": request_id,
                    "sql_results": [
                        {**item, "rows": item["rows"][: settings.schema_context_sample_rows_limit]}
                        for item in sql_results
                    ],
                    "executed_queries": [item.model_dump() for item in executed_queries],
                },
                ensure_ascii=False,
                default=str,
            )
            return responder.answer, [item.model_dump() for item in executed_queries], tool_payload

        if retry_attempt:
            if attempt < settings.planner_retry_limit:
                continue
            return "Não foi possível entender a decisão do planner no momento. Tente novamente.", [], ""

    return "Não foi possível concluir a resposta.", [], ""
