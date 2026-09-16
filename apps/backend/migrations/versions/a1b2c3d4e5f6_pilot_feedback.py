"""pilot feedback (KPI③ PMF — NPS · 유료 전환 의향)

2026-09-16: 이 두 목표를 재는 표가 없어 KPI 가 선언만 남아 있었다.
`usage.record_access` 가 세던 것은 `active_orgs` 하나뿐이다.

Revision ID: a1b2c3d4e5f6
Revises: f62faed65f49
Create Date: 2026-09-16
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "f62faed65f49"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pilot_feedback",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("org_id", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.String(length=32), nullable=True),
        sa.Column("nps_score", sa.Integer(), nullable=False),
        sa.Column("would_pay", sa.String(length=10), nullable=False),
        sa.Column("comment", sa.String(length=2000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_pilot_feedback_org_id"), "pilot_feedback", ["org_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_pilot_feedback_org_id"), table_name="pilot_feedback")
    op.drop_table("pilot_feedback")
