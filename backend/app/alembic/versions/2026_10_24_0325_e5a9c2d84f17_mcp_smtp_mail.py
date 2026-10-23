"""mcp smtp and mail log

Revision ID: e5a9c2d84f17
Revises: c8d4f1a07e53
Create Date: 2026-10-24 03:25:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e5a9c2d84f17"
down_revision: str | None = "c8d4f1a07e53"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _mixin_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("uuid", sa.String(length=64), nullable=False, comment="UUID全局唯一标识"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, comment="是否已删除(0:未删除 1:已删除)"),
        sa.Column("created_time", sa.DateTime(timezone=True), nullable=False, comment="创建时间"),
        sa.Column("updated_time", sa.DateTime(timezone=True), nullable=False, comment="更新时间"),
        sa.Column("deleted_time", sa.DateTime(timezone=True), nullable=True, comment="删除时间"),
    ]


def upgrade() -> None:
    op.create_table(
        "mcp_smtp_config",
        sa.Column("enabled", sa.Boolean(), nullable=False, comment="是否启用"),
        sa.Column("host", sa.String(length=255), nullable=False, comment="SMTP 主机"),
        sa.Column("port", sa.Integer(), nullable=False, comment="端口"),
        sa.Column("username", sa.String(length=128), nullable=True, comment="账号"),
        sa.Column("password_encrypted", sa.Text(), nullable=False, comment="密码密文"),
        sa.Column("from_address", sa.String(length=255), nullable=False, comment="发件人地址"),
        sa.Column("from_name", sa.String(length=128), nullable=True, comment="发件人名称"),
        sa.Column("encryption", sa.String(length=16), nullable=False, comment="加密方式"),
        *_mixin_columns(),
        sa.PrimaryKeyConstraint("id", name="pk_mcp_smtp_config"),
        comment="SMTP 配置表",
    )
    op.create_index("ix_mcp_smtp_config_id", "mcp_smtp_config", ["id"], unique=False)
    op.create_index("ix_mcp_smtp_config_uuid", "mcp_smtp_config", ["uuid"], unique=True)
    op.create_index("ix_mcp_smtp_config_is_deleted", "mcp_smtp_config", ["is_deleted"], unique=False)
    op.create_index("ix_mcp_smtp_config_created_time", "mcp_smtp_config", ["created_time"], unique=False)

    op.create_table(
        "mcp_mail_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("user_id", sa.Integer(), nullable=False, comment="业务用户ID"),
        sa.Column("group_id", sa.Integer(), nullable=False, comment="MCP 组ID"),
        sa.Column("channel", sa.String(length=16), nullable=False, comment="途径"),
        sa.Column("ok", sa.Boolean(), nullable=False, comment="是否成功"),
        sa.Column("reason", sa.String(length=255), nullable=True, comment="失败原因"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, comment="创建时间"),
        sa.PrimaryKeyConstraint("id", name="pk_mcp_mail_log"),
        comment="MCP 发信记录表",
    )
    op.create_index("ix_mcp_mail_log_user_id", "mcp_mail_log", ["user_id"], unique=False)
    op.create_index("ix_mcp_mail_log_group_id", "mcp_mail_log", ["group_id"], unique=False)
    op.create_index("ix_mcp_mail_log_channel", "mcp_mail_log", ["channel"], unique=False)
    op.create_index("ix_mcp_mail_log_ok", "mcp_mail_log", ["ok"], unique=False)
    op.create_index("ix_mcp_mail_log_created_at", "mcp_mail_log", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_mcp_mail_log_created_at", table_name="mcp_mail_log")
    op.drop_index("ix_mcp_mail_log_ok", table_name="mcp_mail_log")
    op.drop_index("ix_mcp_mail_log_channel", table_name="mcp_mail_log")
    op.drop_index("ix_mcp_mail_log_group_id", table_name="mcp_mail_log")
    op.drop_index("ix_mcp_mail_log_user_id", table_name="mcp_mail_log")
    op.drop_table("mcp_mail_log")
    op.drop_index("ix_mcp_smtp_config_created_time", table_name="mcp_smtp_config")
    op.drop_index("ix_mcp_smtp_config_is_deleted", table_name="mcp_smtp_config")
    op.drop_index("ix_mcp_smtp_config_uuid", table_name="mcp_smtp_config")
    op.drop_index("ix_mcp_smtp_config_id", table_name="mcp_smtp_config")
    op.drop_table("mcp_smtp_config")
