"""add sms tokens and purchases

Revision ID: c8e9f0a1b2c3
Revises: a1b2c3d4e5f6
"""
from alembic import op
import sqlalchemy as sa

revision = "c8e9f0a1b2c3"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("sms_tokens", sa.Integer(), nullable=False, server_default="0"))
    op.create_table(
        "sms_purchases",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("tokens", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("checkout_request_id", sa.String(length=100), nullable=True),
        sa.Column("merchant_request_id", sa.String(length=100), nullable=True),
        sa.Column("mpesa_receipt", sa.String(length=100), nullable=True),
        sa.Column("result_code", sa.String(length=20), nullable=True),
        sa.Column("result_description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_sms_purchases_user_id", "sms_purchases", ["user_id"])
    op.create_index("ix_sms_purchases_status", "sms_purchases", ["status"])
    op.create_index("ix_sms_purchases_checkout_request_id", "sms_purchases", ["checkout_request_id"], unique=True)
    op.create_unique_constraint("uq_sms_purchases_mpesa_receipt", "sms_purchases", ["mpesa_receipt"])


def downgrade():
    op.drop_constraint("uq_sms_purchases_mpesa_receipt", "sms_purchases", type_="unique")
    op.drop_index("ix_sms_purchases_checkout_request_id", table_name="sms_purchases")
    op.drop_index("ix_sms_purchases_status", table_name="sms_purchases")
    op.drop_index("ix_sms_purchases_user_id", table_name="sms_purchases")
    op.drop_table("sms_purchases")
    op.drop_column("users", "sms_tokens")
