from datetime import datetime
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
    text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from app.db import Base

EMBEDDING_DIM = 1536


class Connection(Base):
    __tablename__ = "connections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    host: Mapped[str] = mapped_column(String(200), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False, default=5432)
    database: Mapped[str] = mapped_column(String(200), nullable=False)
    username: Mapped[str] = mapped_column(String(200), nullable=False)
    password_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    ssl_mode: Mapped[str] = mapped_column(String(50), nullable=False, default="prefer")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), onupdate=func.now()
    )

    scans: Mapped[list["Scan"]] = relationship(back_populates="connection", cascade="all, delete-orphan")


class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    connection_id: Mapped[int] = mapped_column(ForeignKey("connections.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)

    connection: Mapped[Connection] = relationship(back_populates="scans")
    schemas: Mapped[list["DbSchema"]] = relationship(back_populates="scan", cascade="all, delete-orphan")


class DbSchema(Base):
    __tablename__ = "db_schemas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scan_id: Mapped[int] = mapped_column(ForeignKey("scans.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    scan: Mapped[Scan] = relationship(back_populates="schemas")
    tables: Mapped[list["DbTable"]] = relationship(back_populates="schema", cascade="all, delete-orphan")


class DbTable(Base):
    __tablename__ = "db_tables"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    schema_id: Mapped[int] = mapped_column(ForeignKey("db_schemas.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    table_type: Mapped[str] = mapped_column(String(50), nullable=False, default="BASE TABLE")
    description: Mapped[str | None] = mapped_column(Text)
    annotations: Mapped[dict | None] = mapped_column(JSONB)
    updated_by: Mapped[str | None] = mapped_column(String(100))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), onupdate=func.now()
    )

    schema: Mapped[DbSchema] = relationship(back_populates="tables")
    columns: Mapped[list["DbColumn"]] = relationship(back_populates="table", cascade="all, delete-orphan")
    samples: Mapped[list["Sample"]] = relationship(back_populates="table", cascade="all, delete-orphan")


class DbColumn(Base):
    __tablename__ = "db_columns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    table_id: Mapped[int] = mapped_column(ForeignKey("db_tables.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    data_type: Mapped[str] = mapped_column(String(200), nullable=False)
    is_nullable: Mapped[bool] = mapped_column(Boolean, default=True)
    default: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    annotations: Mapped[dict | None] = mapped_column(JSONB)
    updated_by: Mapped[str | None] = mapped_column(String(100))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), onupdate=func.now()
    )

    table: Mapped[DbTable] = relationship(back_populates="columns")


class DbConstraint(Base):
    __tablename__ = "db_constraints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    table_id: Mapped[int] = mapped_column(ForeignKey("db_tables.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    constraint_type: Mapped[str] = mapped_column(String(50), nullable=False)
    definition: Mapped[str] = mapped_column(Text, nullable=False)


class DbIndex(Base):
    __tablename__ = "db_indexes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    table_id: Mapped[int] = mapped_column(ForeignKey("db_tables.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    definition: Mapped[str] = mapped_column(Text, nullable=False)


class DbView(Base):
    __tablename__ = "db_views"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    schema_id: Mapped[int] = mapped_column(ForeignKey("db_schemas.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    definition: Mapped[str] = mapped_column(Text)


class Sample(Base):
    __tablename__ = "samples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    table_id: Mapped[int] = mapped_column(ForeignKey("db_tables.id"), nullable=False)
    rows: Mapped[list] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    table: Mapped[DbTable] = relationship(back_populates="samples")


class ApiRoute(Base):
    __tablename__ = "api_routes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    path: Mapped[str] = mapped_column(String(500), nullable=False)
    method: Mapped[str] = mapped_column(String(20), nullable=False)
    headers_template: Mapped[dict | None] = mapped_column(JSONB)
    auth_type: Mapped[str] = mapped_column(String(50), nullable=False, default="none")
    body_template: Mapped[dict | None] = mapped_column(JSONB)
    query_params_template: Mapped[dict | None] = mapped_column(JSONB)
    description: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list | None] = mapped_column(JSONB)
    updated_by: Mapped[str | None] = mapped_column(String(100))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), onupdate=func.now()
    )

    fields: Mapped[list["ApiRouteField"]] = relationship(back_populates="route", cascade="all, delete-orphan")


class ApiRouteField(Base):
    __tablename__ = "api_route_fields"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    route_id: Mapped[int] = mapped_column(ForeignKey("api_routes.id"), nullable=False)
    location: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    data_type: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    annotations: Mapped[dict | None] = mapped_column(JSONB)

    route: Mapped[ApiRoute] = relationship(back_populates="fields")


class Embedding(Base):
    __tablename__ = "embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_type: Mapped[str] = mapped_column(String(50), nullable=False)
    item_id: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))
    meta: Mapped[dict | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str | None] = mapped_column(String(500))
    template: Mapped[str | None] = mapped_column(String(200))
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    base_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    rag_prompt: Mapped[str | None] = mapped_column(Text)
    enable_rag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allow_db: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allow_apis: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    connection_ids: Mapped[list[int]] = mapped_column(JSONB, nullable=False, default=list)
    api_route_ids: Mapped[list[int]] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), onupdate=func.now()
    )

    messages: Mapped[list["AgentMessage"]] = relationship(back_populates="agent", cascade="all, delete-orphan")


class AgentMessage(Base):
    __tablename__ = "agent_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    agent: Mapped[Agent] = relationship(back_populates="messages")
