"""unique upstream tool remote name

Revision ID: b6e2d8a14c90
Revises: c3a9e1d84b72
Create Date: 2026-10-24 00:20:00

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b6e2d8a14c90"
down_revision: str | None = "c3a9e1d84b72"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONSTRAINT = "uq_mcp_upstream_tool_upstream_id_remote_name"


def upgrade() -> None:
    # 普通唯一约束，包含已软删除的行。SQLite 不能 ALTER 加约束，走 batch 重建。
    with op.batch_alter_table("mcp_upstream_tool") as batch_op:
        batch_op.create_unique_constraint(_CONSTRAINT, ["upstream_id", "remote_name"])


def downgrade() -> None:
    with op.batch_alter_table("mcp_upstream_tool") as batch_op:
        batch_op.drop_constraint(_CONSTRAINT, type_="unique")
