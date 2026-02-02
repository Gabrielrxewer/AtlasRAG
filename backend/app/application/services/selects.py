"""Gera selects sugeridos a partir de metadados das tabelas."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def _normalize_tags(value: Any) -> list[str]:
    """Normaliza tags para comparação consistente."""
    if not value:
        return []
    if isinstance(value, str):
        return [value.lower().strip()]
    if isinstance(value, list):
        return [str(tag).lower().strip() for tag in value if tag]
    return [str(value).lower().strip()]


def _column_entry(column: str | dict[str, Any]) -> tuple[str, list[str]]:
    """Extrai nome e tags para uma coluna."""
    if isinstance(column, dict):
        name = str(column.get("name") or "")
        tags = _normalize_tags(column.get("tags"))
        return name, tags
    return str(column), []


def _is_likely_id(name: str, tags: list[str]) -> bool:
    """Heurística para colunas de identificação."""
    needles = {"id", "uuid", "code", "identifier", "chave"}
    return bool({name.lower()} & needles or any(tag in needles for tag in tags) or name.lower().endswith("_id"))


def _is_likely_label(name: str, tags: list[str]) -> bool:
    """Heurística para colunas descritivas."""
    needles = {"name", "title", "label", "descricao", "description"}
    return bool({name.lower()} & needles or any(tag in needles for tag in tags))


def _is_likely_status(name: str, tags: list[str]) -> bool:
    """Heurística para colunas de status."""
    needles = {"status", "state", "situacao", "flag"}
    return bool({name.lower()} & needles or any(tag in needles for tag in tags))


def _is_time_column(name: str, tags: list[str]) -> bool:
    """Heurística para colunas temporais."""
    needles = {"created_at", "updated_at", "timestamp", "data", "date", "datetime", "time"}
    return bool(any(needle in name.lower() for needle in needles) or any(tag in needles for tag in tags))


def _distinct_sample_values(sample_rows: list[dict[str, Any]] | None, column_name: str) -> list[Any]:
    """Coleta valores distintos para sugerir filtros."""
    if not sample_rows:
        return []
    values = []
    for row in sample_rows:
        if column_name in row:
            value = row.get(column_name)
            if value is not None and value not in values:
                values.append(value)
        if len(values) >= 6:
            break
    return values


def build_suggested_selects(
    schema_name: str,
    table_name: str,
    columns: Iterable[str | dict[str, Any]],
    table_annotations: dict | None = None,
    sample_rows: list[dict[str, Any]] | None = None,
) -> list[str]:
    """Cria uma lista de selects baseados em heurísticas simples."""
    column_entries = [_column_entry(col) for col in columns if col]
    column_list = [name for name, _ in column_entries if name]
    tags_map = {name: tags for name, tags in column_entries if name}

    # Prioriza colunas mais úteis para inspeção rápida.
    prioritized: list[str] = []
    for name in column_list:
        tags = tags_map.get(name, [])
        if _is_likely_id(name, tags):
            prioritized.append(name)
    for name in column_list:
        tags = tags_map.get(name, [])
        if _is_likely_label(name, tags) and name not in prioritized:
            prioritized.append(name)
    for name in column_list:
        tags = tags_map.get(name, [])
        if _is_likely_status(name, tags) and name not in prioritized:
            prioritized.append(name)
    for name in column_list:
        tags = tags_map.get(name, [])
        if _is_time_column(name, tags) and name not in prioritized:
            prioritized.append(name)
    for name in column_list:
        if name not in prioritized:
            prioritized.append(name)

    preview_columns = prioritized[:6]
    select_columns = ", ".join(preview_columns) if preview_columns else "*"
    selects = [f"SELECT {select_columns} FROM {schema_name}.{table_name} LIMIT 100;"]

    table_tags = _normalize_tags((table_annotations or {}).get("tags"))
    if preview_columns:
        # Sugere filtro baseado em coluna identificadora ou com poucos valores.
        filter_candidates = [
            col
            for col in preview_columns
            if _is_likely_id(col, tags_map.get(col, [])) or _is_likely_status(col, tags_map.get(col, []))
        ]
        if not filter_candidates and sample_rows:
            for col in preview_columns:
                distinct = _distinct_sample_values(sample_rows, col)
                if 0 < len(distinct) <= 5:
                    filter_candidates.append(col)
                    break

        if filter_candidates:
            filter_column = filter_candidates[0]
            selects.append(
                f"SELECT {select_columns} FROM {schema_name}.{table_name} "
                f"WHERE {filter_column} = :{filter_column} LIMIT 50;"
            )

    time_columns = [col for col in preview_columns if _is_time_column(col, tags_map.get(col, []))]
    if time_columns:
        selects.append(
            f"SELECT {select_columns} FROM {schema_name}.{table_name} ORDER BY {time_columns[0]} DESC LIMIT 50;"
        )

    if "fact" in table_tags or "fato" in table_tags or "metric" in table_tags:
        numeric_candidates = [
            col for col in preview_columns if any(tag in {"value", "valor", "amount", "total"} for tag in tags_map.get(col, []))
        ]
        if numeric_candidates:
            selects.append(
                f"SELECT {numeric_candidates[0]}, COUNT(*) AS total FROM {schema_name}.{table_name} "
                f"GROUP BY {numeric_candidates[0]} ORDER BY total DESC LIMIT 25;"
            )

    return selects
