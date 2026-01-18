from __future__ import annotations

import hashlib
from typing import Any
import httpx
from sqlalchemy.orm import Session
from sqlalchemy import select, delete, tuple_

from app.config import settings
from app.models import DbTable, DbColumn, ApiRoute, Embedding


def _hash_content(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _openai_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }


def build_table_document(table: DbTable) -> dict[str, Any]:
    annotations = table.annotations or {}
    content = {
        "type": "table",
        "id": table.id,
        "schema": table.schema.name,
        "name": table.name,
        "description": table.description or "",
        "annotations": annotations,
    }
    return {"content": content, "text": _stringify_content(content)}


def build_column_document(column: DbColumn) -> dict[str, Any]:
    annotations = column.annotations or {}
    content = {
        "type": "column",
        "id": column.id,
        "table": f"{column.table.schema.name}.{column.table.name}",
        "name": column.name,
        "data_type": column.data_type,
        "description": column.description or "",
        "annotations": annotations,
    }
    return {"content": content, "text": _stringify_content(content)}


def build_api_document(route: ApiRoute) -> dict[str, Any]:
    header_keys = list((route.headers_template or {}).keys())
    body_keys = list((route.body_template or {}).keys())
    query_keys = list((route.query_params_template or {}).keys())
    content = {
        "type": "api_route",
        "id": route.id,
        "name": route.name,
        "method": route.method,
        "path": route.path,
        "base_url": route.base_url,
        "description": route.description or "",
        "auth_type": route.auth_type,
        "header_keys": header_keys,
        "body_keys": body_keys,
        "query_param_keys": query_keys,
        "tags": route.tags or [],
    }
    return {"content": content, "text": _stringify_content(content)}


def _stringify_content(content: dict[str, Any]) -> str:
    return "\n".join(f"{key}: {value}" for key, value in content.items())


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required")
    payload = {"input": texts, "model": "text-embedding-3-small"}
    with httpx.Client(timeout=30) as client:
        response = client.post(
            "https://api.openai.com/v1/embeddings",
            headers=_openai_headers(),
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
    return [item["embedding"] for item in data["data"]]


def reindex_embeddings(db: Session, scan_id: int | None, include_api_routes: bool) -> int:
    query_tables = select(DbTable)
    query_columns = select(DbColumn)
    if scan_id:
        query_tables = query_tables.join(DbTable.schema).where(DbTable.schema.has(scan_id=scan_id))
        query_columns = query_columns.join(DbColumn.table).join(DbTable.schema).where(DbTable.schema.has(scan_id=scan_id))

    tables = db.scalars(query_tables).all()
    columns = db.scalars(query_columns).all()
    routes = db.scalars(select(ApiRoute)).all() if include_api_routes else []

    documents: list[dict[str, Any]] = []
    for table in tables:
        documents.append(build_table_document(table))
    for column in columns:
        documents.append(build_column_document(column))
    for route in routes:
        documents.append(build_api_document(route))

    if not documents:
        return 0

    delete_targets = [(doc["content"]["type"], doc["content"]["id"]) for doc in documents]
    existing = db.scalars(
        select(Embedding).where(tuple_(Embedding.item_type, Embedding.item_id).in_(delete_targets))
    ).all()
    existing_map = {(item.item_type, item.item_id): item for item in existing}

    to_index: list[dict[str, Any]] = []
    for doc in documents:
        content_hash = _hash_content(doc["text"])
        doc["content_hash"] = content_hash
        key = (doc["content"]["type"], doc["content"]["id"])
        if key in existing_map and existing_map[key].content_hash == content_hash:
            continue
        to_index.append(doc)

    if not to_index:
        return 0

    delete_targets = [(doc["content"]["type"], doc["content"]["id"]) for doc in to_index]
    db.execute(
        delete(Embedding).where(
            tuple_(Embedding.item_type, Embedding.item_id).in_(delete_targets)
        )
    )

    embeddings = embed_texts([doc["text"] for doc in to_index])
    for doc, vector in zip(to_index, embeddings):
        content_hash = doc["content_hash"]
        db.add(
            Embedding(
                item_type=doc["content"]["type"],
                item_id=doc["content"]["id"],
                content_hash=content_hash,
                embedding=vector,
                metadata=doc["content"],
            )
        )
    db.commit()
    return len(to_index)


def search_embeddings(db: Session, question: str, top_k: int) -> list[Embedding]:
    vector = embed_texts([question])[0]
    return db.query(Embedding).order_by(Embedding.embedding.cosine_distance(vector)).limit(top_k).all()


def ask_rag(db: Session, question: str) -> dict[str, Any]:
    matches = search_embeddings(db, question, settings.rag_top_k)
    context = [match.metadata for match in matches]
    instructions = (
        "Você é um assistente de catálogo de dados e APIs. "
        "Use apenas o contexto fornecido. Se não houver contexto suficiente, "
        "peça clarificação e mencione o que foi encontrado. "
        "Retorne referências usando os IDs internos fornecidos."
    )
    messages = [
        {"role": "system", "content": instructions},
        {"role": "user", "content": f"Contexto: {context}\nPergunta: {question}"},
    ]
    payload = {
        "model": settings.openai_model,
        "messages": messages,
        "temperature": 0.2,
    }
    with httpx.Client(timeout=60) as client:
        response = client.post(
            "https://api.openai.com/v1/chat/completions",
            headers=_openai_headers(),
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

    answer = data["choices"][0]["message"]["content"]
    citations = [{"item_type": match.item_type, "item_id": match.item_id} for match in matches]
    return {"answer": answer, "citations": citations}
