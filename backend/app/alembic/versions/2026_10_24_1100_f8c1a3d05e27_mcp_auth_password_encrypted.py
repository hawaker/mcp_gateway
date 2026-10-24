"""mcp auth basic password encrypted at rest

Revision ID: f8c1a3d05e27
Revises: d4f8a2c19e70
Create Date: 2026-10-24 11:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f8c1a3d05e27"
down_revision: str | None = "d4f8a2c19e70"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "mcp_biz_auth_config",
        "password",
        new_column_name="password_encrypted",
        existing_type=sa.String(length=512),
        existing_nullable=True,
        comment="Basic 密码密文",
    )


def downgrade() -> None:
    op.alter_column(
        "mcp_biz_auth_config",
        "password_encrypted",
        new_column_name="password",
        existing_type=sa.String(length=512),
        existing_nullable=True,
        comment="Basic 密码",
    )
