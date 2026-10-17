"""Initial schema.

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-17
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "clients",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("client_type", sa.String(16), nullable=False),
        sa.Column("contact_person", sa.String(200), nullable=True),
        sa.Column("phone", sa.String(32), nullable=True),
        sa.Column("email", sa.String(254), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("source", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_archived", sa.Boolean(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("search_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "client_type IN ('person','company')",
            name="client_type",
        ),
        sa.CheckConstraint(
            "status IN ('lead','active','inactive','lost')",
            name="client_status",
        ),
    )
    op.create_index(
        "ix_clients_deleted_archived_status",
        "clients",
        ["deleted_at", "is_archived", "status"],
    )
    op.create_index("ix_clients_search_text", "clients", ["search_text"])
    op.create_index("ix_clients_updated_at", "clients", ["updated_at"])

    op.create_table(
        "deals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=True),
        sa.Column("expected_close_date", sa.Date(), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lost_reason", sa.String(500), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("search_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["clients.id"],
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "status IN ('new','in_progress','proposal',"
            "'negotiation','won','lost')",
            name="deal_status",
        ),
    )
    op.create_index(
        "ix_deals_deleted_status",
        "deals",
        ["deleted_at", "status"],
    )
    op.create_index("ix_deals_client_id", "deals", ["client_id"])
    op.create_index("ix_deals_search_text", "deals", ["search_text"])
    op.create_index("ix_deals_updated_at", "deals", ["updated_at"])

    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("number", sa.String(20), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("deal_id", sa.Integer(), nullable=True),
        sa.Column("client_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=True),
        sa.Column("order_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["deal_id"],
            ["deals.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["clients.id"],
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("number"),
        sa.CheckConstraint(
            "status IN ('new','confirmed','in_progress',"
            "'completed','cancelled')",
            name="order_status",
        ),
    )
    op.create_index(
        "ix_orders_deleted_status",
        "orders",
        ["deleted_at", "status"],
    )
    op.create_index("ix_orders_deal_id", "orders", ["deal_id"])
    op.create_index("ix_orders_client_id", "orders", ["client_id"])

    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("task_type", sa.String(16), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("all_day", sa.Boolean(), nullable=False),
        sa.Column("is_done", sa.Boolean(), nullable=False),
        sa.Column("done_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("client_id", sa.Integer(), nullable=True),
        sa.Column("deal_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["clients.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["deal_id"],
            ["deals.id"],
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "task_type IN ('call','meeting','email','todo','other')",
            name="task_type",
        ),
    )
    op.create_index(
        "ix_tasks_deleted_done_due",
        "tasks",
        ["deleted_at", "is_done", "due_at"],
    )
    op.create_index("ix_tasks_client_id", "tasks", ["client_id"])
    op.create_index("ix_tasks_deal_id", "tasks", ["deal_id"])

    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "google_oauth_credentials",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_email", sa.String(254), nullable=True),
        sa.Column("scopes", sa.Text(), nullable=True),
        sa.Column("refresh_token_encrypted", sa.LargeBinary(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "last_refresh_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "last_error_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_table(
        "export_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entity", sa.String(32), nullable=False),
        sa.Column("file_id", sa.String(128), nullable=True),
        sa.Column("file_name", sa.String(255), nullable=True),
        sa.Column("file_url", sa.String(512), nullable=True),
        sa.Column("folder_id", sa.String(128), nullable=True),
        sa.Column("rows", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("filters", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("export_log")
    op.drop_table("google_oauth_credentials")
    op.drop_table("app_settings")
    op.drop_table("tasks")
    op.drop_table("orders")
    op.drop_table("deals")
    op.drop_table("clients")
