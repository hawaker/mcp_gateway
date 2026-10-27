"""genbi soft-delete friendly partial unique indexes

Revision ID: c9d5e3f02b16
Revises: b8c4d2e91a05
Create Date: 2026-10-27 11:38:00

Replace full unique constraints with partial unique indexes
WHERE is_deleted = false so soft-deleted rows do not block recreate.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c9d5e3f02b16"
down_revision: str | None = "b8c4d2e91a05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ACTIVE = sa.text("is_deleted = false")


def upgrade() -> None:
    op.drop_constraint("uq_genbi_project_datasource_id", "genbi_project", type_="unique")
    op.create_index(
        "uq_genbi_project_datasource_id",
        "genbi_project",
        ["datasource_id"],
        unique=True,
        postgresql_where=_ACTIVE,
    )

    op.drop_constraint("uq_genbi_view_project_id_name", "genbi_view", type_="unique")
    op.create_index(
        "uq_genbi_view_project_id_name",
        "genbi_view",
        ["project_id", "name"],
        unique=True,
        postgresql_where=_ACTIVE,
    )

    op.drop_constraint("uq_genbi_metric_project_id_name", "genbi_metric", type_="unique")
    op.create_index(
        "uq_genbi_metric_project_id_name",
        "genbi_metric",
        ["project_id", "name"],
        unique=True,
        postgresql_where=_ACTIVE,
    )


def downgrade() -> None:
    op.drop_index("uq_genbi_metric_project_id_name", table_name="genbi_metric")
    op.create_unique_constraint(
        "uq_genbi_metric_project_id_name",
        "genbi_metric",
        ["project_id", "name"],
    )

    op.drop_index("uq_genbi_view_project_id_name", table_name="genbi_view")
    op.create_unique_constraint(
        "uq_genbi_view_project_id_name",
        "genbi_view",
        ["project_id", "name"],
    )

    op.drop_index("uq_genbi_project_datasource_id", table_name="genbi_project")
    op.create_unique_constraint(
        "uq_genbi_project_datasource_id",
        "genbi_project",
        ["datasource_id"],
    )
