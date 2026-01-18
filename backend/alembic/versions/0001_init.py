"""init

Revision ID: 0001
Revises: 
Create Date: 2024-05-01
"""

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "connections",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("host", sa.String(200), nullable=False),
        sa.Column("port", sa.Integer, nullable=False),
        sa.Column("database", sa.String(200), nullable=False),
        sa.Column("username", sa.String(200), nullable=False),
        sa.Column("password_encrypted", sa.Text, nullable=False),
        sa.Column("ssl_mode", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime, server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "scans",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("connection_id", sa.Integer, sa.ForeignKey("connections.id"), nullable=False),
        sa.Column("status", sa.String(50), server_default=sa.text("'running'"), nullable=False),
        sa.Column("started_at", sa.DateTime, server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime, nullable=True),
    )

    op.create_table(
        "db_schemas",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("scan_id", sa.Integer, sa.ForeignKey("scans.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
    )

    op.create_table(
        "db_tables",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("schema_id", sa.Integer, sa.ForeignKey("db_schemas.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("table_type", sa.String(50), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("annotations", sa.dialects.postgresql.JSONB, nullable=True),
        sa.Column("updated_by", sa.String(100), nullable=True),
        sa.Column("updated_at", sa.DateTime, server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "db_columns",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("table_id", sa.Integer, sa.ForeignKey("db_tables.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("data_type", sa.String(200), nullable=False),
        sa.Column("is_nullable", sa.Boolean, nullable=False),
        sa.Column("default", sa.Text, nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("annotations", sa.dialects.postgresql.JSONB, nullable=True),
        sa.Column("updated_by", sa.String(100), nullable=True),
        sa.Column("updated_at", sa.DateTime, server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "db_constraints",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("table_id", sa.Integer, sa.ForeignKey("db_tables.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("constraint_type", sa.String(50), nullable=False),
        sa.Column("definition", sa.Text, nullable=False),
    )

    op.create_table(
        "db_indexes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("table_id", sa.Integer, sa.ForeignKey("db_tables.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("definition", sa.Text, nullable=False),
    )

    op.create_table(
        "db_views",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("schema_id", sa.Integer, sa.ForeignKey("db_schemas.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("definition", sa.Text, nullable=True),
    )

    op.create_table(
        "samples",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("table_id", sa.Integer, sa.ForeignKey("db_tables.id"), nullable=False),
        sa.Column("rows", sa.dialects.postgresql.JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "api_routes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("base_url", sa.String(500), nullable=False),
        sa.Column("path", sa.String(500), nullable=False),
        sa.Column("method", sa.String(20), nullable=False),
        sa.Column("headers_template", sa.dialects.postgresql.JSONB, nullable=True),
        sa.Column("auth_type", sa.String(50), nullable=False),
        sa.Column("body_template", sa.dialects.postgresql.JSONB, nullable=True),
        sa.Column("query_params_template", sa.dialects.postgresql.JSONB, nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("tags", sa.dialects.postgresql.JSONB, nullable=True),
        sa.Column("updated_by", sa.String(100), nullable=True),
        sa.Column("updated_at", sa.DateTime, server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "api_route_fields",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("route_id", sa.Integer, sa.ForeignKey("api_routes.id"), nullable=False),
        sa.Column("location", sa.String(50), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("data_type", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("annotations", sa.dialects.postgresql.JSONB, nullable=True),
    )

    op.create_table(
        "embeddings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("item_type", sa.String(50), nullable=False),
        sa.Column("item_id", sa.Integer, nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("metadata", sa.dialects.postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("embeddings")
    op.drop_table("api_route_fields")
    op.drop_table("api_routes")
    op.drop_table("samples")
    op.drop_table("db_views")
    op.drop_table("db_indexes")
    op.drop_table("db_constraints")
    op.drop_table("db_columns")
    op.drop_table("db_tables")
    op.drop_table("db_schemas")
    op.drop_table("scans")
    op.drop_table("connections")
