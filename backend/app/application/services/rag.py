"""Serviços RAG para embeddings, reindexação e consulta."""
from __future__ import annotations

import hashlib
from typing import Any
import httpx
from sqlalchemy.orm import Session
from sqlalchemy import select, delete, tuple_

from app.core.config import settings
from app.domain.models import DbTable, DbColumn, ApiRoute, Embedding, Scan, DbSchema
from app.application.services.selects import build_suggested_selects


def _hash_content(value: str) -> str:
    """Hash determinístico do conteúdo para deduplicação."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _openai_headers() -> dict[str, str]:
    """Headers padrão para APIs da OpenAI."""
    return {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }


def build_table_document(table: DbTable) -> dict[str, Any]:
    """Serializa tabela para documento de embedding."""
    annotations = table.annotations or {}
    sample_rows = table.samples[0].rows if table.samples else None
    connection_id = table.schema.scan.connection_id if table.schema and table.schema.scan else None
    scan_id = table.schema.scan_id if table.schema else None
    suggested_selects = build_suggested_selects(
        table.schema.name,
        table.name,
        [{"name": column.name, "tags": (column.annotations or {}).get("tags")} for column in table.columns],
        table_annotations=annotations,
        sample_rows=sample_rows,
    )
    content = {
        "type": "table",
        "id": table.id,
        "schema": table.schema.name,
        "name": table.name,
        "connection_id": connection_id,
        "scan_id": scan_id,
        "description": table.description or "",
        "annotations": annotations,
        "suggested_selects": suggested_selects,
    }
    return {"content": content, "text": _stringify_content(content)}


def build_column_document(column: DbColumn) -> dict[str, Any]:
    """Serializa coluna para documento de embedding."""
    annotations = column.annotations or {}
    connection_id = (
        column.table.schema.scan.connection_id
        if column.table and column.table.schema and column.table.schema.scan
        else None
    )
    scan_id = column.table.schema.scan_id if column.table and column.table.schema else None
    content = {
        "type": "column",
        "id": column.id,
        "connection_id": connection_id,
        "scan_id": scan_id,
        "table": f"{column.table.schema.name}.{column.table.name}",
        "name": column.name,
        "data_type": column.data_type,
        "description": column.description or "",
        "annotations": annotations,
    }
    return {"content": content, "text": _stringify_content(content)}


def build_api_document(route: ApiRoute) -> dict[str, Any]:
    """Serializa rota de API para documento de embedding."""
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
    """Transforma dict em texto descritivo para embeddings."""
    return "\n".join(f"{key}: {value}" for key, value in content.items())


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Gera embeddings para uma lista de textos."""
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
    """Reindexa embeddings para tabelas/colunas/APIs."""
    query_tables = select(DbTable)
    query_columns = select(DbColumn)
    if scan_id:
        query_tables = query_tables.join(DbTable.schema).where(DbTable.schema.has(scan_id=scan_id))
        query_columns = query_columns.join(DbColumn.table).join(DbTable.schema).where(DbTable.schema.has(scan_id=scan_id))

    tables = db.scalars(query_tables).all()
    columns = db.scalars(query_columns).all()
    routes = db.scalars(select(ApiRoute)).all() if include_api_routes else []

    # Monta documentos para cada entidade do catálogo.
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
        # Pula reindexação quando conteúdo não mudou.
        content_hash = _hash_content(doc["text"])
        doc["content_hash"] = content_hash
        key = (doc["content"]["type"], doc["content"]["id"])
        if key in existing_map and existing_map[key].content_hash == content_hash:
            continue
        to_index.append(doc)

    if not to_index:
        return 0

    delete_targets = [(doc["content"]["type"], doc["content"]["id"]) for doc in to_index]
    # Remove embeddings antigos antes de inserir os novos.
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
                meta=doc["content"],
            )
        )
    db.commit()
    return len(to_index)


def _latest_scan_ids(db: Session, connection_ids: set[int]) -> set[int]:
    """Retorna o último scan concluído por conexão."""
    if not connection_ids:
        return set()
    scans = (
        db.query(Scan)
        .filter(Scan.connection_id.in_(connection_ids), Scan.status == "completed")
        .order_by(Scan.connection_id, Scan.finished_at.desc().nullslast(), Scan.started_at.desc())
        .all()
    )
    latest: dict[int, int] = {}
    for scan in scans:
        if scan.connection_id not in latest:
            latest[scan.connection_id] = scan.id
    return set(latest.values())


def _resolve_table_meta(db: Session, table_ids: set[int]) -> dict[int, dict[str, Any]]:
    """Enriquece metadata de tabelas sem conexão registrada."""
    if not table_ids:
        return {}
    rows = (
        db.query(DbTable.id, DbSchema.scan_id, Scan.connection_id)
        .join(DbTable.schema)
        .join(DbSchema.scan)
        .filter(DbTable.id.in_(table_ids))
        .all()
    )
    return {row.id: {"scan_id": row.scan_id, "connection_id": row.connection_id} for row in rows}


def _resolve_column_meta(db: Session, column_ids: set[int]) -> dict[int, dict[str, Any]]:
    """Enriquece metadata de colunas sem conexão registrada."""
    if not column_ids:
        return {}
    rows = (
        db.query(DbColumn.id, DbSchema.scan_id, Scan.connection_id)
        .join(DbColumn.table)
        .join(DbTable.schema)
        .join(DbSchema.scan)
        .filter(DbColumn.id.in_(column_ids))
        .all()
    )
    return {row.id: {"scan_id": row.scan_id, "connection_id": row.connection_id} for row in rows}


def search_embeddings(db: Session, question: str, top_k: int, scope: dict[str, Any] | None = None) -> list[Embedding]:
    """Busca embeddings mais próximos com filtro opcional de escopo."""
    vector = embed_texts([question])[0]
    distance = Embedding.embedding.cosine_distance(vector)
    limit = top_k
    if scope and (scope.get("connection_ids") or scope.get("api_route_ids")):
        limit = top_k * 20
    results = (
        db.query(Embedding, distance.label("distance"))
        .order_by(distance)
        .limit(limit)
        .all()
    )
    # cosine_distance: menor é mais similar; filtra pelo limiar configurado.
    filtered = [item for item, dist in results if dist is not None and dist <= settings.rag_min_score]
    if scope:
        connection_ids = set(scope.get("connection_ids") or [])
        api_route_ids = set(scope.get("api_route_ids") or [])
        latest_scan_ids = _latest_scan_ids(db, connection_ids)
        fallback_table_ids: set[int] = set()
        fallback_column_ids: set[int] = set()
        for item, _ in results:
            if item.item_type == "table" and not (item.meta or {}).get("connection_id"):
                fallback_table_ids.add(item.item_id)
            elif item.item_type == "column" and not (item.meta or {}).get("connection_id"):
                fallback_column_ids.add(item.item_id)
        fallback_table_meta = _resolve_table_meta(db, fallback_table_ids)
        fallback_column_meta = _resolve_column_meta(db, fallback_column_ids)
        if connection_ids or api_route_ids:
            # Filtra candidatos respeitando o escopo e último scan.
            scoped_candidates: list[tuple[Embedding, float]] = []
            for item, dist in results:
                if item.item_type in {"table", "column"} and connection_ids:
                    meta = item.meta or {}
                    if item.item_type == "table":
                        meta = {**fallback_table_meta.get(item.item_id, {}), **meta}
                    else:
                        meta = {**fallback_column_meta.get(item.item_id, {}), **meta}
                    connection_id = meta.get("connection_id")
                    scan_id = meta.get("scan_id")
                    if connection_id in connection_ids and (not latest_scan_ids or scan_id in latest_scan_ids):
                        scoped_candidates.append((item, dist))
                elif item.item_type == "api_route" and api_route_ids:
                    if item.item_id in api_route_ids:
                        scoped_candidates.append((item, dist))
            scoped = [item for item, dist in scoped_candidates if dist is not None and dist <= settings.rag_min_score]
            if not scoped and scoped_candidates:
                scoped = [item for item, _ in scoped_candidates[:top_k]]
            filtered = scoped
    return filtered[:top_k]


def ask_rag(db: Session, question: str, scope: dict[str, Any] | None = None) -> dict[str, Any]:
    """Consulta o RAG e retorna resposta com citações."""
    matches = search_embeddings(db, question.strip(), settings.rag_top_k, scope=scope)
    if not matches:
        if scope and scope.get("connection_ids"):
            latest_scan_ids = _latest_scan_ids(db, set(scope.get("connection_ids") or []))
            if not latest_scan_ids:
                return {
                    "answer": "Nenhum scan concluído foi encontrado para as conexões selecionadas.",
                    "citations": [],
                }
            return {
                "answer": (
                    "O último scan das conexões selecionadas ainda não foi indexado no RAG. "
                    "Reindexe o catálogo para atualizar o contexto."
                ),
                "citations": [],
            }
        return {"answer": "Contexto insuficiente para responder com segurança.", "citations": []}
    # Usa contexto das matches para o prompt.
    context = [match.meta for match in matches]
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
