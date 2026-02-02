"""scan error message

Revision ID: 0007
Revises: 0006
Create Date: 2024-10-09
"""

from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("scans", sa.Column("error_message", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("scans", "error_message")
