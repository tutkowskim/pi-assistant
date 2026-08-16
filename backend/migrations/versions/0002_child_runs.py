"""Track child-agent runs.

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("runs") as batch_op:
        batch_op.add_column(sa.Column("parent_run_id", sa.String(36), nullable=True))
        batch_op.create_foreign_key(
            "fk_runs_parent_run_id", "runs", ["parent_run_id"], ["id"], ondelete="SET NULL"
        )
        batch_op.create_index("ix_runs_parent_run_id", ["parent_run_id"])


def downgrade() -> None:
    with op.batch_alter_table("runs") as batch_op:
        batch_op.drop_index("ix_runs_parent_run_id")
        batch_op.drop_constraint("fk_runs_parent_run_id", type_="foreignkey")
        batch_op.drop_column("parent_run_id")
