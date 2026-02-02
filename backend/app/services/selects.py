from __future__ import annotations

from collections.abc import Iterable


def build_suggested_selects(schema_name: str, table_name: str, columns: Iterable[str]) -> list[str]:
    column_list = [col for col in columns if col]
    preview_columns = column_list[:5]
    select_columns = ", ".join(preview_columns) if preview_columns else "*"
    selects = [f"SELECT {select_columns} FROM {schema_name}.{table_name} LIMIT 100;"]
    if preview_columns:
        first_column = preview_columns[0]
        selects.append(
            f"SELECT {select_columns} FROM {schema_name}.{table_name} "
            f"WHERE {first_column} = :{first_column} LIMIT 1;"
        )
    if "created_at" in column_list:
        selects.append(f"SELECT {select_columns} FROM {schema_name}.{table_name} ORDER BY created_at DESC LIMIT 50;")
    return selects
