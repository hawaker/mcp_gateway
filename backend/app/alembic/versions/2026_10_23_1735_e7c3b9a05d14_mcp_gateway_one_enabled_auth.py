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
    bind = op.get_bind()
    # MySQL 没有部分索引。函数索引在 enabled 为假时得到 NULL，多条未启用记录可以并存。
    if bind.dialect.name == "mysql":
        op.execute("CREATE UNIQUE INDEX uq_mcp_biz_auth_config_one_enabled ON mcp_biz_auth_config ((CASE WHEN enabled = 1 THEN system_id ELSE NULL END))")
        return
    where = sa.text("enabled IS TRUE") if bind.dialect.name == "postgresql" else sa.text("enabled = 1")
    dialect_where = {"postgresql_where": where} if bind.dialect.name == "postgresql" else {"sqlite_where": where}
    op.create_index(
        "uq_mcp_biz_auth_config_one_enabled",
        "mcp_biz_auth_config",
        ["system_id"],
        unique=True,
        **dialect_where,
    )


def downgrade() -> None:
    op.drop_index("uq_mcp_biz_auth_config_one_enabled", table_name="mcp_biz_auth_config")
