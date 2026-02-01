"""agents

Revision ID: 0006
Revises: 0005
Create Date: 2024-10-08
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agents",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("role", sa.String(500), nullable=True),
        sa.Column("template", sa.String(200), nullable=True),
        sa.Column("model", sa.String(200), nullable=False),
        sa.Column("base_prompt", sa.Text, nullable=False),
        sa.Column("rag_prompt", sa.Text, nullable=True),
        sa.Column("enable_rag", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("allow_db", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("allow_apis", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("connection_ids", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("api_route_ids", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "agent_messages",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("agent_id", sa.Integer, sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("agent_messages")
    op.drop_table("agents")
