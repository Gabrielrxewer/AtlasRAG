from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class ConnectionCreate(BaseModel):
    name: str
    host: str
    port: int = 5432
    database: str
    username: str
    password: str
    ssl_mode: str = "prefer"


class ConnectionUpdate(BaseModel):
    name: str | None = None
    host: str | None = None
    port: int | None = None
    database: str | None = None
    username: str | None = None
    password: str | None = None
    ssl_mode: str | None = None


class ConnectionOut(BaseModel):
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
    id: int
    connection_id: int
    status: str
    started_at: datetime
    finished_at: datetime | None
    error_message: str | None = None

    class Config:
        from_attributes = True


class SchemaTable(BaseModel):
    id: int
    schema: str
    name: str
    table_type: str
    description: str | None
    annotations: dict | None


class ColumnOut(BaseModel):
    id: int
    table_id: int
    name: str
    data_type: str
    is_nullable: bool
    default: str | None
    description: str | None
    annotations: dict | None


class TableSchemaOut(BaseModel):
    id: int
    schema: str
    name: str
    table_type: str
    description: str | None
    annotations: dict | None
    columns: list[ColumnOut]
    suggested_selects: list[str] = Field(default_factory=list)


class SampleOut(BaseModel):
    id: int
    table_id: int
    rows: list
    created_at: datetime

    class Config:
        from_attributes = True


class AnnotationUpdate(BaseModel):
    description: str | None = None
    annotations: dict | None = None
    updated_by: str | None = None


class ApiRouteCreate(BaseModel):
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
    location: str
    name: str
    data_type: str
    description: str | None = None
    annotations: dict | None = None


class ApiRouteOut(ApiRouteCreate):
    id: int
    updated_by: str | None = None
    updated_at: datetime
    fields: list[ApiRouteFieldIn] = Field(default_factory=list)

    class Config:
        from_attributes = True


class ApiRouteAnnotationUpdate(BaseModel):
    description: str | None = None
    tags: list[str] | None = None
    updated_by: str | None = None
    fields: list[ApiRouteFieldIn] | None = None


class RagAskIn(BaseModel):
    question: str
    scope: dict[str, Any] | None = None


class RagAskOut(BaseModel):
    answer: str
    citations: list[dict]


class RagIndexIn(BaseModel):
    scan_id: int | None = None
    include_api_routes: bool = True


class AgentCreate(BaseModel):
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
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AgentMessageCreate(BaseModel):
    content: str


class AgentMessageOut(BaseModel):
    id: int
    agent_id: int
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class AgentChatResponse(BaseModel):
    message: AgentMessageOut
    citations: list[dict] = Field(default_factory=list)
