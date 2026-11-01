import json
import uuid
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import select

from src.models import Account, Payment, PaymentStatus, LedgerEntry, OutboxEvent
from src.models.ledger_entry import EntryType


class InsufficientFundsError(Exception):
    pass


class AccountNotFoundError(Exception):
    pass


class DuplicatePaymentError(Exception):
    def __init__(self, existing: Payment):
        self.existing = existing
        super().__init__(f"Payment {existing.idempotency_key} already exists")


class InvalidTransitionError(Exception):
    pass


def create_payment(
    db: Session,
    *,
    idempotency_key: str,
    source_account_id: uuid.UUID,
    dest_account_id: uuid.UUID,
    amount: Decimal,
    currency: str,
) -> Payment:
    # Idempotency — return existing if this key was already processed
    existing = db.scalar(
        select(Payment).where(Payment.idempotency_key == idempotency_key)
    )
    if existing:
        raise DuplicatePaymentError(existing)

    source = db.scalar(select(Account).where(Account.id == source_account_id))
    dest = db.scalar(select(Account).where(Account.id == dest_account_id))

    if not source:
        raise AccountNotFoundError(f"Source account {source_account_id} not found")
    if not dest:
        raise AccountNotFoundError(f"Destination account {dest_account_id} not found")

    payment = Payment(
        idempotency_key=idempotency_key,
        source_account_id=source_account_id,
        dest_account_id=dest_account_id,
        amount=amount,
        currency=currency,
        status=PaymentStatus.PENDING,
    )
    db.add(payment)

    # Write event to transactional outbox in same transaction
    outbox = OutboxEvent(
        event_type="payment.created",
        payload=json.dumps(
            {
                "payment_id": str(payment.id),
                "source_account_id": str(source_account_id),
                "dest_account_id": str(dest_account_id),
                "amount": str(amount),
                "currency": currency,
            }
        ),
    )
    db.add(outbox)
    db.flush()
    return payment


def process_payment(db: Session, *, payment_id: uuid.UUID) -> Payment:
    """
    Called by the SQS consumer Lambda. Locks both account rows in ascending-id
    order to prevent deadlocks, validates funds, posts ledger entries, and
    updates balances atomically.
    """
    payment = db.scalar(select(Payment).where(Payment.id == payment_id))
    if not payment:
        raise ValueError(f"Payment {payment_id} not found")

    if not payment.can_transition_to(PaymentStatus.PROCESSING):
        raise InvalidTransitionError(
            f"Cannot move {payment.status} → PROCESSING"
        )

    # Lock accounts in consistent order to avoid deadlock under concurrent payments
    account_ids = sorted(
        [payment.source_account_id, payment.dest_account_id], key=lambda x: str(x)
    )
    accounts = {
        str(a.id): a
        for a in db.scalars(
            select(Account)
            .where(Account.id.in_(account_ids))
            .with_for_update()
        )
    }

    source = accounts[str(payment.source_account_id)]
    dest = accounts[str(payment.dest_account_id)]

    if source.balance < payment.amount:
        payment.status = PaymentStatus.FAILED
        payment.failure_reason = "Insufficient funds"
        db.flush()
        return payment

    payment.status = PaymentStatus.PROCESSING
    source.balance -= payment.amount
    dest.balance += payment.amount

    db.add(LedgerEntry(
        payment_id=payment.id,
        account_id=source.id,
        entry_type=EntryType.DEBIT,
        amount=payment.amount,
        currency=payment.currency,
        description=f"Payment {payment.id} — debit",
    ))
    db.add(LedgerEntry(
        payment_id=payment.id,
        account_id=dest.id,
        entry_type=EntryType.CREDIT,
        amount=payment.amount,
        currency=payment.currency,
        description=f"Payment {payment.id} — credit",
    ))

    payment.status = PaymentStatus.COMPLETED

    outbox = OutboxEvent(
        event_type="payment.completed",
        payload=json.dumps({"payment_id": str(payment.id)}),
    )
    db.add(outbox)
    db.flush()
    return payment


def get_payment(db: Session, payment_id: uuid.UUID) -> Payment | None:
    return db.scalar(select(Payment).where(Payment.id == payment_id))


def list_payments(db: Session, account_id: uuid.UUID, limit: int = 50) -> list[Payment]:
    return list(
        db.scalars(
            select(Payment)
            .where(
                (Payment.source_account_id == account_id)
                | (Payment.dest_account_id == account_id)
            )
            .order_by(Payment.created_at.desc())
            .limit(limit)
        )
    )
