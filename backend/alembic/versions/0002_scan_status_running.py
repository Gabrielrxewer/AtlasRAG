"""scan status default running

Revision ID: 0002
Revises: 0001
Create Date: 2024-05-02
"""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "scans",
        "status",
        existing_type=sa.String(length=50),
        server_default="running",
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "scans",
        "status",
        existing_type=sa.String(length=50),
        server_default=None,
        existing_nullable=False,
    )
