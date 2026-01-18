"""embeddings unique constraint and vector index

Revision ID: 0004
Revises: 0003
Create Date: 2024-05-04
"""

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_embeddings_item_type_item_id",
        "embeddings",
        ["item_type", "item_id"],
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_embeddings_embedding_ivfflat "
        "ON embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_embeddings_embedding_ivfflat")
    op.drop_constraint("uq_embeddings_item_type_item_id", "embeddings", type_="unique")
