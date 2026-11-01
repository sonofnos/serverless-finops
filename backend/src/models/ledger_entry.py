import uuid
import enum
from decimal import Decimal
from sqlalchemy import String, Numeric, Enum, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import mapped_column, Mapped, relationship
from .base import Base, TimestampMixin


class EntryType(str, enum.Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class LedgerEntry(Base, TimestampMixin):
    """Double-entry ledger: every payment posts exactly one DEBIT and one CREDIT."""

    __tablename__ = "ledger_entries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    payment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payments.id"), nullable=False
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False
    )
    entry_type: Mapped[EntryType] = mapped_column(Enum(EntryType), nullable=False)
    amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=2), nullable=False
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    description: Mapped[str] = mapped_column(String(512), nullable=False, default="")

    payment = relationship("Payment", back_populates="ledger_entries")
    account = relationship("Account", back_populates="ledger_entries")

    __table_args__ = (Index("ix_ledger_account_id", "account_id"),)
