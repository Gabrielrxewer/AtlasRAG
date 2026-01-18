"""embeddings indexes

Revision ID: 0005
Revises: 0004
Create Date: 2024-05-05
"""

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_embeddings_item_type_item_id",
        "embeddings",
        ["item_type", "item_id"],
        unique=False,
    )
    op.create_index(
        "ix_embeddings_content_hash",
        "embeddings",
        ["content_hash"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_embeddings_content_hash", table_name="embeddings")
    op.drop_index("ix_embeddings_item_type_item_id", table_name="embeddings")
