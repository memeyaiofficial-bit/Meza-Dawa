"""add SMS transaction ledger

Revision ID: d4e5f6a7b8c9
Revises: c8e9f0a1b2c3
"""
from alembic import op
import sqlalchemy as sa

revision = "d4e5f6a7b8c9"
down_revision = "c8e9f0a1b2c3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "sms_transactions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("recipient", sa.String(length=20), nullable=False),
        sa.Column("message_type", sa.String(length=40), nullable=False, server_default="reminder"),
        sa.Column("tokens_used", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("provider", sa.String(length=40), nullable=False, server_default="talksasa"),
        sa.Column("provider_message_id", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_sms_transactions_user_id", "sms_transactions", ["user_id"])
    op.create_index("ix_sms_transactions_status", "sms_transactions", ["status"])
    op.create_index("ix_sms_transactions_provider_message_id", "sms_transactions", ["provider_message_id"])


def downgrade():
    op.drop_index("ix_sms_transactions_provider_message_id", table_name="sms_transactions")
    op.drop_index("ix_sms_transactions_status", table_name="sms_transactions")
    op.drop_index("ix_sms_transactions_user_id", table_name="sms_transactions")
    op.drop_table("sms_transactions")
