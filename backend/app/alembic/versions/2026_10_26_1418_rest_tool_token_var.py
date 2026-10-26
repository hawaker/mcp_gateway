"""rest tool token_var

Revision ID: a1b2c3d4e5f6
Revises: bbe7d85ef954
Create Date: 2026-10-26 14:18:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "bbe7d85ef954"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("mcp_rest_tool", schema=None) as batch_op:
        batch_op.add_column(sa.Column("token_var", sa.String(length=128), nullable=True, comment="注入的 auth 变量名"))


def downgrade() -> None:
    with op.batch_alter_table("mcp_rest_tool", schema=None) as batch_op:
        batch_op.drop_column("token_var")
