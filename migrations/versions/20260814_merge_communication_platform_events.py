"""Merge the communication and platform event migration branches.

Revision ID: 20260814_merge_comm_events
Revises: 20260730_communication, 20260813_platform_events
Create Date: 2026-08-14 00:00:00.000000
"""

revision = "20260814_merge_comm_events"
down_revision = ("20260730_communication", "20260813_platform_events")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
