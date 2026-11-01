import uuid
import enum
from decimal import Decimal
from sqlalchemy import String, Numeric, Enum, ForeignKey, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import mapped_column, Mapped, relationship
from .base import Base, TimestampMixin


class PaymentStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REVERSED = "REVERSED"


class Payment(Base, TimestampMixin):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Idempotency key — caller-supplied, prevents double-submission
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    source_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False
    )
    dest_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=2), nullable=False
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus), nullable=False, default=PaymentStatus.PENDING
    )
    failure_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    sqs_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    source_account = relationship(
        "Account", foreign_keys=[source_account_id], back_populates="payments_sent"
    )
    dest_account = relationship(
        "Account", foreign_keys=[dest_account_id], back_populates="payments_received"
    )
    ledger_entries = relationship("LedgerEntry", back_populates="payment")

    __table_args__ = (
        Index("ix_payments_status", "status"),
        Index("ix_payments_source_account", "source_account_id"),
    )

    def can_transition_to(self, new_status: PaymentStatus) -> bool:
        allowed: dict[PaymentStatus, set[PaymentStatus]] = {
            PaymentStatus.PENDING: {PaymentStatus.PROCESSING, PaymentStatus.FAILED},
            PaymentStatus.PROCESSING: {PaymentStatus.COMPLETED, PaymentStatus.FAILED},
            PaymentStatus.COMPLETED: {PaymentStatus.REVERSED},
            PaymentStatus.FAILED: set(),
            PaymentStatus.REVERSED: set(),
        }
        return new_status in allowed[self.status]
