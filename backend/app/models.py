from datetime import datetime
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from app.db import Base


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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    scans: Mapped[list["Scan"]] = relationship(back_populates="connection", cascade="all, delete-orphan")


class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    connection_id: Mapped[int] = mapped_column(ForeignKey("connections.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)

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
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

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
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    embedding: Mapped[list[float]] = mapped_column(Vector(1536))
    metadata: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
