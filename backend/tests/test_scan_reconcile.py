from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.services.scan import reconcile_scan_status
from app.services import sql_orchestrator
from app.services.scan import build_sample_query


@dataclass
class FakeScan:
    id: int
    connection_id: int
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None


class FakeResult:
    def __init__(self, value: int):
        self._value = value

    def scalar_one(self):
        return self._value


class FakeQuery:
    def __init__(self, items):
        self._items = items

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return list(self._items)


class FakeSession:
    def __init__(self, scans, counts):
        self._scans = scans
        self._counts = counts
        self.committed = False

    def query(self, _model):
        return FakeQuery(self._scans)

    def execute(self, _statement, params):
        scan_id = params["scan_id"]
        return FakeResult(self._counts.get(scan_id, 0))

    def commit(self):
        self.committed = True


def test_reconcile_scan_status_marks_completed():
    started = datetime.now(timezone.utc) - timedelta(minutes=10)
    scans = [FakeScan(id=1, connection_id=10, status="running", started_at=started)]
    db = FakeSession(scans, counts={1: 3})
    reconcile_scan_status(db, connection_ids=[10], stale_minutes=5)
    assert scans[0].status == "completed"
    assert scans[0].finished_at is not None
    assert scans[0].error_message is None
    assert db.committed is True


def test_reconcile_scan_status_marks_failed():
    started = datetime.now(timezone.utc) - timedelta(minutes=10)
    scans = [FakeScan(id=2, connection_id=11, status="running", started_at=started)]
    db = FakeSession(scans, counts={2: 0})
    reconcile_scan_status(db, connection_ids=[11], stale_minutes=5)
    assert scans[0].status == "failed"
    assert scans[0].finished_at is not None
    assert scans[0].error_message == "Scan interrompido/sem catálogo gerado"
    assert db.committed is True


def test_select_latest_scan_ids_prefers_completed_and_running_with_catalog():
    scans = [
        FakeScan(id=3, connection_id=12, status="running"),
        FakeScan(id=4, connection_id=12, status="completed"),
        FakeScan(id=5, connection_id=13, status="running"),
    ]
    db = FakeSession(scans, counts={3: 2, 5: 1})
    latest, running = sql_orchestrator._select_latest_scan_ids(db, scans)
    assert latest[12] == 4
    assert latest[13] == 5
    assert running == {5}


def test_build_sample_query_accepts_quoted_names():
    query = build_sample_query('Sales-Data', 'Order Items', ['Line ID'])
    assert query is not None
    assert 'FROM "Sales-Data"."Order Items"' in query
    assert 'ORDER BY "Line ID"' in query
