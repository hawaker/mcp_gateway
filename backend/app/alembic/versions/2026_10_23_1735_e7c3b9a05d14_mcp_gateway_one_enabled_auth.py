"""one enabled auth config per system

Revision ID: e7c3b9a05d14
Revises: b8e1d4c07f25
Create Date: 2026-10-23 17:35:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e7c3b9a05d14"
down_revision: str | None = "b8e1d4c07f25"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 与模型相同的函数唯一索引。enabled 为假时表达式为 NULL，三个方言都允许多个 NULL。
    op.create_index(
        "uq_mcp_biz_auth_config_one_enabled",
        "mcp_biz_auth_config",
        [sa.text("(CASE WHEN enabled THEN system_id ELSE NULL END)")],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_mcp_biz_auth_config_one_enabled", table_name="mcp_biz_auth_config")
