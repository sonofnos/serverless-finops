import uuid
from decimal import Decimal
from sqlalchemy import String, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import mapped_column, Mapped, relationship
from .base import Base, TimestampMixin


class Account(Base, TimestampMixin):
    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    owner_id: Mapped[str] = mapped_column(String(128), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    balance: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=2), nullable=False, default=Decimal("0.00")
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    payments_sent = relationship(
        "Payment", foreign_keys="Payment.source_account_id", back_populates="source_account"
    )
    payments_received = relationship(
        "Payment", foreign_keys="Payment.dest_account_id", back_populates="dest_account"
    )
    ledger_entries = relationship("LedgerEntry", back_populates="account")

    __table_args__ = (UniqueConstraint("owner_id", "currency", name="uq_account_owner_currency"),)
