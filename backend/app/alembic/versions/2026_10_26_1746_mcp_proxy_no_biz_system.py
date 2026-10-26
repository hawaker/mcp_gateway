"""mcp proxy: drop system_id, add code/name, call_log.upstream_id

Revision ID: f7e8d9c0b1a2
Revises: cefb85f65447
Create Date: 2026-10-26 17:46:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f7e8d9c0b1a2"
down_revision: Union[str, None] = "cefb85f65447"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM mcp_group_tool WHERE source = 'upstream'"))
    bind.execute(sa.text("DELETE FROM mcp_upstream_tool"))
    bind.execute(sa.text("DELETE FROM mcp_upstream_mcp"))

    bind.execute(sa.text("DROP INDEX IF EXISTS ix_mcp_upstream_mcp_system_id"))
    bind.execute(
        sa.text(
            "ALTER TABLE mcp_upstream_mcp DROP CONSTRAINT IF EXISTS fk_mcp_upstream_mcp_system_id_mcp_biz_system"
        )
    )
    bind.execute(sa.text("ALTER TABLE mcp_upstream_mcp DROP COLUMN IF EXISTS system_id"))
    bind.execute(
        sa.text(
            "ALTER TABLE mcp_upstream_mcp ADD COLUMN IF NOT EXISTS name VARCHAR(128) NOT NULL DEFAULT ''"
        )
    )
    bind.execute(
        sa.text(
            "ALTER TABLE mcp_upstream_mcp ADD COLUMN IF NOT EXISTS code VARCHAR(64) NOT NULL DEFAULT ''"
        )
    )
    bind.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_mcp_upstream_mcp_name ON mcp_upstream_mcp (name)"))
    bind.execute(sa.text("CREATE UNIQUE INDEX IF NOT EXISTS ix_mcp_upstream_mcp_code ON mcp_upstream_mcp (code)"))
    bind.execute(sa.text("ALTER TABLE mcp_upstream_mcp ALTER COLUMN name DROP DEFAULT"))
    bind.execute(sa.text("ALTER TABLE mcp_upstream_mcp ALTER COLUMN code DROP DEFAULT"))
    # comments
    bind.execute(sa.text("COMMENT ON COLUMN mcp_upstream_mcp.name IS '名称'"))
    bind.execute(sa.text("COMMENT ON COLUMN mcp_upstream_mcp.code IS '英文编码'"))

    bind.execute(sa.text("ALTER TABLE mcp_call_log ADD COLUMN IF NOT EXISTS upstream_id INTEGER"))
    bind.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_mcp_call_log_upstream_id ON mcp_call_log (upstream_id)"))
    bind.execute(sa.text("COMMENT ON COLUMN mcp_call_log.upstream_id IS 'MCP 代理ID'"))


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DROP INDEX IF EXISTS ix_mcp_call_log_upstream_id"))
    bind.execute(sa.text("ALTER TABLE mcp_call_log DROP COLUMN IF EXISTS upstream_id"))

    bind.execute(sa.text("DELETE FROM mcp_group_tool WHERE source = 'upstream'"))
    bind.execute(sa.text("DELETE FROM mcp_upstream_tool"))
    bind.execute(sa.text("DELETE FROM mcp_upstream_mcp"))

    bind.execute(sa.text("DROP INDEX IF EXISTS ix_mcp_upstream_mcp_code"))
    bind.execute(sa.text("DROP INDEX IF EXISTS ix_mcp_upstream_mcp_name"))
    bind.execute(sa.text("ALTER TABLE mcp_upstream_mcp DROP COLUMN IF EXISTS code"))
    bind.execute(sa.text("ALTER TABLE mcp_upstream_mcp DROP COLUMN IF EXISTS name"))
    bind.execute(
        sa.text(
            "ALTER TABLE mcp_upstream_mcp ADD COLUMN IF NOT EXISTS system_id INTEGER NOT NULL DEFAULT 0"
        )
    )
    bind.execute(
        sa.text(
            "ALTER TABLE mcp_upstream_mcp DROP CONSTRAINT IF EXISTS fk_mcp_upstream_mcp_system_id_mcp_biz_system"
        )
    )
    bind.execute(
        sa.text(
            "ALTER TABLE mcp_upstream_mcp ADD CONSTRAINT fk_mcp_upstream_mcp_system_id_mcp_biz_system "
            "FOREIGN KEY (system_id) REFERENCES mcp_biz_system(id) ON DELETE CASCADE ON UPDATE CASCADE"
        )
    )
    bind.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_mcp_upstream_mcp_system_id ON mcp_upstream_mcp (system_id)"))
    bind.execute(sa.text("ALTER TABLE mcp_upstream_mcp ALTER COLUMN system_id DROP DEFAULT"))
