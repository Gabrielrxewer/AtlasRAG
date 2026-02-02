"""Testes de coerção de encoding em scans."""
import logging

import pytest

from app.application.services.scan import _coerce_text


def test_coerce_text_fallback_logs_warning(caplog):
    # Garante decodificação resiliente.
    value = b"caf\xe9"
    with caplog.at_level(logging.WARNING, logger="atlasrag.scan"):
        decoded = _coerce_text(
            value,
            scan_id=42,
            object_type="table",
            field_name="name",
            schema_name="public",
        )
    assert decoded == "café"
    assert any(record.message == "scan_text_decode_fallback" for record in caplog.records)
