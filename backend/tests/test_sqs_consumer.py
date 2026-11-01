"""
Tests for the SQS consumer Lambda, using moto to mock AWS SQS locally.
"""
import json
import os
import uuid
from decimal import Decimal
import pytest
import boto3
from moto import mock_aws

from src.services.account_service import create_account
from src.services.payment_service import create_payment


@pytest.fixture(autouse=True)
def patch_db(db, monkeypatch):
    monkeypatch.setattr("src.consumers.payment_consumer.get_session", lambda: db)


@pytest.fixture
def accounts(db):
    a = create_account(db, owner_id="sqs-a", name="Alice")
    b = create_account(db, owner_id="sqs-b", name="Bob")
    a.balance = Decimal("1000.00")
    db.flush()
    return a, b


def _sqs_event(payment_id: str) -> dict:
    return {
        "Records": [
            {
                "messageId": str(uuid.uuid4()),
                "body": json.dumps({
                    "event_type": "payment.created",
                    "payment_id": payment_id,
                }),
            }
        ]
    }


class TestPaymentConsumer:
    def test_processes_payment_and_returns_no_failures(self, db, accounts):
        from src.consumers.payment_consumer import handler
        a, b = accounts
        payment = create_payment(
            db,
            idempotency_key=f"sqs-{uuid.uuid4()}",
            source_account_id=a.id,
            dest_account_id=b.id,
            amount=Decimal("100.00"),
            currency="USD",
        )
        result = handler(_sqs_event(str(payment.id)), None)
        assert result["batchItemFailures"] == []

    def test_idempotent_retry_does_not_fail(self, db, accounts):
        """Re-delivering the same SQS message must not cause a batch failure."""
        from src.consumers.payment_consumer import handler
        a, b = accounts
        payment = create_payment(
            db,
            idempotency_key=f"sqs-idem-{uuid.uuid4()}",
            source_account_id=a.id,
            dest_account_id=b.id,
            amount=Decimal("50.00"),
            currency="USD",
        )
        evt = _sqs_event(str(payment.id))
        handler(evt, None)  # first delivery — completes payment
        result = handler(evt, None)  # second delivery — already COMPLETED
        assert result["batchItemFailures"] == []

    def test_bad_payment_id_goes_to_failures(self, db):
        from src.consumers.payment_consumer import handler
        evt = {
            "Records": [{
                "messageId": "bad-msg",
                "body": json.dumps({
                    "event_type": "payment.created",
                    "payment_id": str(uuid.uuid4()),  # doesn't exist
                }),
            }]
        }
        result = handler(evt, None)
        assert any(f["itemIdentifier"] == "bad-msg" for f in result["batchItemFailures"])

    def test_unknown_event_type_skipped_not_failed(self, db):
        from src.consumers.payment_consumer import handler
        evt = {
            "Records": [{
                "messageId": "unknown-type",
                "body": json.dumps({"event_type": "something.unknown"}),
            }]
        }
        result = handler(evt, None)
        assert result["batchItemFailures"] == []


@mock_aws
class TestOutboxPublisher:
    def test_publishes_unpublished_events_to_sqs(self, db, accounts, monkeypatch):
        from src.consumers.outbox_publisher import handler
        from src.models import OutboxEvent
        from sqlalchemy import select

        os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
        os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
        os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")

        sqs = boto3.client("sqs", region_name="us-east-1")
        queue = sqs.create_queue(
            QueueName="test-queue.fifo",
            Attributes={"FifoQueue": "true", "ContentBasedDeduplication": "true"},
        )
        queue_url = queue["QueueUrl"]

        os.environ["PAYMENT_QUEUE_URL"] = queue_url
        os.environ["AWS_REGION"] = "us-east-1"

        monkeypatch.setattr("src.consumers.outbox_publisher.get_session", lambda: db)
        monkeypatch.setattr("src.consumers.outbox_publisher._sqs", None)

        a, b = accounts
        create_payment(
            db,
            idempotency_key=f"outbox-{uuid.uuid4()}",
            source_account_id=a.id,
            dest_account_id=b.id,
            amount=Decimal("10.00"),
            currency="USD",
        )

        handler({}, None)

        events = list(db.scalars(select(OutboxEvent).where(OutboxEvent.published == True)))  # noqa
        assert len(events) >= 1
