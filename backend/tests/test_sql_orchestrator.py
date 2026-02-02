import json
from dataclasses import dataclass

from app.config import settings
from app.services import sql_orchestrator


def test_validate_sql_enforces_safety_and_limit():
    allowed_tables = {"public.assets", "assets"}
    ok, error, safe_sql = sql_orchestrator._validate_sql(
        "SELECT id FROM public.assets", allowed_tables, max_rows=5
    )
    assert ok is True
    assert safe_sql.endswith("LIMIT 5")

    ok, error, _ = sql_orchestrator._validate_sql(
        "UPDATE public.assets SET name = 'x'", allowed_tables, max_rows=5
    )
    assert ok is False
    assert error == "Apenas SELECT/CTE são permitidos."

    ok, error, _ = sql_orchestrator._validate_sql(
        "SELECT * FROM public.assets; SELECT * FROM public.assets",
        allowed_tables,
        max_rows=5,
    )
    assert ok is False
    assert error == "Múltiplas statements não são permitidas."

    ok, error, _ = sql_orchestrator._validate_sql(
        "SELECT * FROM public.assets FOR UPDATE", allowed_tables, max_rows=5
    )
    assert ok is False
    assert error == "SELECT com FOR UPDATE/SHARE não é permitido."

    ok, error, safe_sql = sql_orchestrator._validate_sql(
        "SELECT * FROM public.assets LIMIT 1000", allowed_tables, max_rows=5
    )
    assert ok is True
    assert "LIMIT 5" in safe_sql


def test_orchestrate_sql_rag_smoke(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    monkeypatch.setattr(sql_orchestrator, "reconcile_scan_status", lambda *_args, **_kwargs: None)

    def fake_schema_context(_db, _connection_ids):
        return (
            {
                "connections": [
                    {
                        "connection_id": 1,
                        "tables": [
                            {
                                "schema": "public",
                                "name": "assets",
                                "columns": [{"name": "id"}, {"name": "name"}],
                                "sample_rows": [],
                            }
                        ],
                        "constraints": [],
                        "indexes": [],
                    }
                ]
            },
            {1: {"public.assets", "assets"}},
        )

    planner_payload = {
        "decision": "run_selects",
        "reason": "Usuário pediu listar 5 assets.",
        "entities": ["assets"],
        "queries": [
            {
                "name": "listar_assets",
                "purpose": "Listar 5 assets.",
                "sql": "SELECT id, name FROM public.assets LIMIT 5",
                "connection_id": 1,
            }
        ],
        "predefined_query_id": None,
        "clarifying_question": None,
    }
    responder_payload = {
        "answer": "Encontrei 5 assets: Asset A, Asset B, Asset C, Asset D e Asset E.",
        "used_sql": [
            {
                "name": "listar_assets",
                "sql": "SELECT id, name FROM public.assets LIMIT 5",
                "rows_returned": 5,
            }
        ],
        "assumptions": [],
        "caveats": [],
        "followups": [],
    }

    def fake_call_llm(_model, messages, response_format=None):
        if "Planner SQL-RAG" in messages[0]["content"]:
            return json.dumps(planner_payload, ensure_ascii=False)
        return json.dumps(responder_payload, ensure_ascii=False)

    monkeypatch.setattr(sql_orchestrator, "_schema_context", fake_schema_context)
    monkeypatch.setattr(sql_orchestrator, "_call_llm", fake_call_llm)
    monkeypatch.setattr(sql_orchestrator, "_connection_info", lambda _conn: {})
    monkeypatch.setattr(
        sql_orchestrator,
        "_build_engine",
        lambda *_args, **_kwargs: FakeEngine(
            [
                {"id": 1, "name": "Asset A"},
                {"id": 2, "name": "Asset B"},
                {"id": 3, "name": "Asset C"},
                {"id": 4, "name": "Asset D"},
                {"id": 5, "name": "Asset E"},
            ]
        ),
    )

    fake_db = FakeSession(FakeConnection(id=1))
    answer, executed, tool_payload = sql_orchestrator.orchestrate_sql_rag(
        fake_db,
        "quais assets nós temos na tabela? cite 5",
        [1],
        [],
        "system prompt",
    )

    assert "Encontrei 5 assets" in answer
    assert executed[0]["rows_returned"] == 5
    assert "LIMIT 5" in executed[0]["sql"]
    assert tool_payload


def test_orchestrate_sql_rag_planner_invalid_fallback(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    monkeypatch.setattr(sql_orchestrator, "reconcile_scan_status", lambda *_args, **_kwargs: None)

    def fake_schema_context(_db, _connection_ids):
        return (
            {
                "connections": [
                    {
                        "connection_id": 1,
                        "tables": [
                            {
                                "schema": "public",
                                "name": "assets",
                                "columns": [{"name": "id"}, {"name": "name"}],
                                "sample_rows": [],
                            }
                        ],
                        "constraints": [],
                        "indexes": [],
                    }
                ]
            },
            {1: {"public.assets", "assets"}},
        )

    responder_payload = {
        "answer": "Fallback respondeu com assets.",
        "used_sql": [],
        "assumptions": [],
        "caveats": [],
        "followups": [],
    }

    def fake_call_llm(_model, messages, response_format=None):
        if "Planner SQL-RAG" in messages[0]["content"]:
            return "not-json"
        return json.dumps(responder_payload, ensure_ascii=False)

    monkeypatch.setattr(sql_orchestrator, "_schema_context", fake_schema_context)
    monkeypatch.setattr(sql_orchestrator, "_call_llm", fake_call_llm)
    monkeypatch.setattr(sql_orchestrator, "_connection_info", lambda _conn: {})
    monkeypatch.setattr(
        sql_orchestrator,
        "_build_engine",
        lambda *_args, **_kwargs: FakeEngine([{"id": 1, "name": "Asset A"}]),
    )

    fake_db = FakeSession(FakeConnection(id=1))
    answer, executed, tool_payload = sql_orchestrator.orchestrate_sql_rag(
        fake_db,
        "quais assets nós temos na tabela? cite 5",
        [1],
        [],
        "system prompt",
    )

    assert "Fallback respondeu" in answer
    assert executed
    assert "LIMIT 5" in executed[0]["sql"]
    assert tool_payload


@dataclass
class FakeConnection:
    id: int
    updated_at: None = None


class FakeSession:
    def __init__(self, connection: FakeConnection):
        self._connection = connection

    def get(self, _model, connection_id: int):
        if connection_id == self._connection.id:
            return self._connection
        return None


class FakeEngine:
    def __init__(self, rows):
        self._rows = rows

    def connect(self):
        return FakeConnectionContext(self._rows)


class FakeConnectionContext:
    def __init__(self, rows):
        self._rows = rows

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, _statement, _params=None):
        return FakeResult(self._rows)


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def fetchmany(self, _limit):
        return self._rows

    def keys(self):
        if not self._rows:
            return []
        return list(self._rows[0].keys())


def test_orchestrate_sql_rag_without_catalog(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    monkeypatch.setattr(sql_orchestrator, "reconcile_scan_status", lambda *_args, **_kwargs: None)

    def fake_schema_context(_db, _connection_ids):
        return (
            {
                "connections": [
                    {
                        "connection_id": 1,
                        "tables": [],
                        "constraints": [],
                        "indexes": [],
                    }
                ]
            },
            {1: set()},
        )

    monkeypatch.setattr(sql_orchestrator, "_schema_context", fake_schema_context)

    fake_db = FakeSession(FakeConnection(id=1))
    answer, executed, tool_payload = sql_orchestrator.orchestrate_sql_rag(
        fake_db,
        "quais assets nós temos na tabela? cite 5",
        [1],
        [],
        "system prompt",
    )

    assert "Não há catálogo/scan concluído" in answer
    assert executed == []
    assert tool_payload == ""


def test_validate_sql_allows_cte(monkeypatch):
    allowed_tables = {"public.assets", "assets"}
    sql = "WITH tmp AS (SELECT id FROM public.assets) SELECT id FROM tmp"
    ok, error, safe_sql = sql_orchestrator._validate_sql(sql, allowed_tables, max_rows=5)
    assert ok is True
    assert "LIMIT 5" in safe_sql


def test_fallback_top_query(monkeypatch):
    schema_context = {
        "connections": [
            {
                "connection_id": 1,
                "tables": [
                    {
                        "schema": "public",
                        "name": "assets",
                        "columns": [{"name": "id"}, {"name": "value"}, {"name": "name"}],
                    }
                ],
            }
        ]
    }
    response = sql_orchestrator.fallback_plan(
        "qual asset com maior valor?",
        schema_context,
        [1],
        max_rows=10,
    )
    assert response.decision == "run_selects"
    assert "ORDER BY value DESC" in response.queries[0].sql
    assert response.queries[0].sql.endswith("LIMIT 1")


def test_json_dumps_safe_handles_decimal():
    payload = {"value": sql_orchestrator.Decimal("49726.60")}
    rendered = sql_orchestrator._json_dumps_safe(payload)
    assert '"49726.60"' in rendered
