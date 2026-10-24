"""smtp config singleton unique index

Revision ID: d4f8a2c19e70
Revises: e5a9c2d84f17
Create Date: 2026-10-24 10:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4f8a2c19e70"
down_revision: str | None = "e5a9c2d84f17"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 与模型相同的常量唯一索引，保证全表最多一行。
    op.create_index(
        "uq_mcp_smtp_config_singleton",
        "mcp_smtp_config",
        [sa.text("(1)")],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_mcp_smtp_config_singleton", table_name="mcp_smtp_config")
