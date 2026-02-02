"""Schemas Pydantic usados por requests e responses da API."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ConnectionCreate(BaseModel):
    """Payload para criação de conexão."""
    name: str
    host: str
    port: int = 5432
    database: str
    username: str
    password: str
    ssl_mode: str = "prefer"


class ConnectionUpdate(BaseModel):
    """Payload parcial para atualização de conexão."""
    name: str | None = None
    host: str | None = None
    port: int | None = None
    database: str | None = None
    username: str | None = None
    password: str | None = None
    ssl_mode: str | None = None


class ConnectionOut(BaseModel):
    """Resposta com dados de conexão."""
    id: int
    name: str
    host: str
    port: int
    database: str
    username: str
    ssl_mode: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ScanOut(BaseModel):
    """Resposta com status de varreduras."""
    id: int
    connection_id: int
    status: str
    started_at: datetime
    finished_at: datetime | None
    error_message: str | None = None

    class Config:
        from_attributes = True


class SchemaTable(BaseModel):
    """Tabela resumida usada em listagens."""
    id: int
    schema_name: str = Field(validation_alias="schema", serialization_alias="schema")
    name: str
    table_type: str
    description: str | None
    annotations: dict | None


class ColumnOut(BaseModel):
    """Resposta com metadados de coluna."""
    id: int
    table_id: int
    name: str
    data_type: str
    is_nullable: bool
    default: str | None
    description: str | None
    annotations: dict | None


class TableSchemaOut(BaseModel):
    """Schema completo da tabela com colunas e sugestões."""
    id: int
    schema_name: str = Field(validation_alias="schema", serialization_alias="schema")
    name: str
    table_type: str
    description: str | None
    annotations: dict | None
    columns: list[ColumnOut]
    suggested_selects: list[str] = Field(default_factory=list)


class SampleOut(BaseModel):
    """Amostras retornadas para visualização."""
    id: int
    table_id: int
    rows: list
    created_at: datetime

    class Config:
        from_attributes = True


class AnnotationUpdate(BaseModel):
    """Payload de atualização de anotações."""
    description: str | None = None
    annotations: dict | None = None
    updated_by: str | None = None


class ApiRouteCreate(BaseModel):
    """Payload para cadastrar rota de API."""
    name: str
    base_url: str
    path: str
    method: str
    headers_template: dict | None = None
    auth_type: str = "none"
    body_template: dict | None = None
    query_params_template: dict | None = None
    description: str | None = None
    tags: list[str] | None = None


class ApiRouteFieldIn(BaseModel):
    """Campo de rota de API para documentação."""
    location: str
    name: str
    data_type: str
    description: str | None = None
    annotations: dict | None = None


class ApiRouteOut(ApiRouteCreate):
    """Resposta completa de rota com campos."""
    id: int
    updated_by: str | None = None
    updated_at: datetime
    fields: list[ApiRouteFieldIn] = Field(default_factory=list)

    class Config:
        from_attributes = True


class ApiRouteAnnotationUpdate(BaseModel):
    """Atualização de descrição/tags/campos da rota."""
    description: str | None = None
    tags: list[str] | None = None
    updated_by: str | None = None
    fields: list[ApiRouteFieldIn] | None = None


class RagScope(BaseModel):
    """Escopo de busca RAG por conexões e APIs."""
    connection_ids: list[int] | None = None
    api_route_ids: list[int] | None = None


class RagAskIn(BaseModel):
    """Pergunta enviada ao RAG."""
    question: str
    scope: RagScope | None = None


class RagAskOut(BaseModel):
    """Resposta do RAG com citações."""
    answer: str
    citations: list[dict]
    selects: list[dict] = Field(default_factory=list)


class RagIndexIn(BaseModel):
    """Payload para reindexar embeddings."""
    scan_id: int | None = None
    include_api_routes: bool = True


class AgentCreate(BaseModel):
    """Payload para criar agentes."""
    name: str
    role: str | None = None
    template: str | None = None
    model: str
    base_prompt: str
    rag_prompt: str | None = None
    enable_rag: bool = True
    allow_db: bool = True
    allow_apis: bool = True
    connection_ids: list[int] = Field(default_factory=list)
    api_route_ids: list[int] = Field(default_factory=list)


class AgentUpdate(BaseModel):
    """Payload parcial para atualizar agentes."""
    name: str | None = None
    role: str | None = None
    template: str | None = None
    model: str | None = None
    base_prompt: str | None = None
    rag_prompt: str | None = None
    enable_rag: bool | None = None
    allow_db: bool | None = None
    allow_apis: bool | None = None
    connection_ids: list[int] | None = None
    api_route_ids: list[int] | None = None


class AgentOut(AgentCreate):
    """Resposta com dados completos do agente."""
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AgentMessageCreate(BaseModel):
    """Payload para enviar mensagem ao agente."""
    content: str


class AgentMessageOut(BaseModel):
    """Resposta com mensagem registrada."""
    id: int
    agent_id: int
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class AgentChatResponse(BaseModel):
    """Resposta do chat com citações e selects sugeridos."""
    message: AgentMessageOut
    citations: list[dict] = Field(default_factory=list)
    selects: list[dict] = Field(default_factory=list)
