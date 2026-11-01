import uuid
from decimal import Decimal
import pytest

from src.models import Account, Payment, PaymentStatus
from src.services.payment_service import (
    create_payment,
    process_payment,
    get_payment,
    DuplicatePaymentError,
    AccountNotFoundError,
    InvalidTransitionError,
)
from src.services.account_service import create_account


def _make_accounts(db, balance_a=Decimal("1000.00"), balance_b=Decimal("0.00")):
    a = create_account(db, owner_id="user-a", name="Alice", currency="USD")
    b = create_account(db, owner_id="user-b", name="Bob", currency="USD")
    a.balance = balance_a
    b.balance = balance_b
    db.flush()
    return a, b


class TestCreatePayment:
    def test_creates_pending_payment(self, db):
        a, b = _make_accounts(db)
        payment = create_payment(
            db,
            idempotency_key="key-001",
            source_account_id=a.id,
            dest_account_id=b.id,
            amount=Decimal("100.00"),
            currency="USD",
        )
        assert payment.status == PaymentStatus.PENDING
        assert payment.amount == Decimal("100.00")

    def test_idempotency_returns_existing(self, db):
        a, b = _make_accounts(db)
        p1 = create_payment(
            db,
            idempotency_key="key-idem",
            source_account_id=a.id,
            dest_account_id=b.id,
            amount=Decimal("50.00"),
            currency="USD",
        )
        with pytest.raises(DuplicatePaymentError) as exc:
            create_payment(
                db,
                idempotency_key="key-idem",
                source_account_id=a.id,
                dest_account_id=b.id,
                amount=Decimal("50.00"),
                currency="USD",
            )
        assert exc.value.existing.id == p1.id

    def test_raises_if_source_account_missing(self, db):
        _, b = _make_accounts(db)
        with pytest.raises(AccountNotFoundError):
            create_payment(
                db,
                idempotency_key="key-bad-src",
                source_account_id=uuid.uuid4(),
                dest_account_id=b.id,
                amount=Decimal("10.00"),
                currency="USD",
            )

    def test_writes_outbox_event(self, db):
        from src.models import OutboxEvent
        from sqlalchemy import select

        a, b = _make_accounts(db)
        create_payment(
            db,
            idempotency_key="key-outbox",
            source_account_id=a.id,
            dest_account_id=b.id,
            amount=Decimal("25.00"),
            currency="USD",
        )
        events = list(db.scalars(select(OutboxEvent)))
        assert any(e.event_type == "payment.created" for e in events)


class TestProcessPayment:
    def _create_pending(self, db, amount=Decimal("200.00")):
        a, b = _make_accounts(db, balance_a=Decimal("500.00"))
        payment = create_payment(
            db,
            idempotency_key=f"proc-{uuid.uuid4()}",
            source_account_id=a.id,
            dest_account_id=b.id,
            amount=amount,
            currency="USD",
        )
        return payment, a, b

    def test_completes_payment_and_posts_ledger(self, db):
        from src.models import LedgerEntry
        from sqlalchemy import select

        payment, src, dst = self._create_pending(db)
        result = process_payment(db, payment_id=payment.id)

        assert result.status == PaymentStatus.COMPLETED
        assert src.balance == Decimal("300.00")
        assert dst.balance == Decimal("200.00")

        entries = list(
            db.scalars(select(LedgerEntry).where(LedgerEntry.payment_id == payment.id))
        )
        assert len(entries) == 2
        types = {e.entry_type.value for e in entries}
        assert types == {"DEBIT", "CREDIT"}

    def test_fails_on_insufficient_funds(self, db):
        a, b = _make_accounts(db, balance_a=Decimal("10.00"))
        payment = create_payment(
            db,
            idempotency_key=f"insuf-{uuid.uuid4()}",
            source_account_id=a.id,
            dest_account_id=b.id,
            amount=Decimal("999.00"),
            currency="USD",
        )
        result = process_payment(db, payment_id=payment.id)
        assert result.status == PaymentStatus.FAILED
        assert result.failure_reason == "Insufficient funds"
        assert a.balance == Decimal("10.00")  # unchanged

    def test_invalid_transition_raises(self, db):
        payment, _, _ = self._create_pending(db)
        process_payment(db, payment_id=payment.id)  # COMPLETED now
        with pytest.raises(InvalidTransitionError):
            process_payment(db, payment_id=payment.id)

    def test_state_machine_allows_only_valid_transitions(self, db):
        from src.models.payment import PaymentStatus
        p = Payment(
            idempotency_key="sm-test",
            source_account_id=uuid.uuid4(),
            dest_account_id=uuid.uuid4(),
            amount=Decimal("1.00"),
            currency="USD",
            status=PaymentStatus.PENDING,
        )
        assert p.can_transition_to(PaymentStatus.PROCESSING)
        assert not p.can_transition_to(PaymentStatus.COMPLETED)
        assert not p.can_transition_to(PaymentStatus.REVERSED)
