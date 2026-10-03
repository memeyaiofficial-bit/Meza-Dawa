import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, DateTime, Numeric, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class SmsPurchase(Base):
    __tablename__ = "sms_purchases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    checkout_request_id: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True, index=True)
    merchant_request_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mpesa_receipt: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)
    result_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    result_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User", backref="sms_purchases")
