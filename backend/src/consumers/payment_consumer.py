"""
SQS Consumer Lambda — triggered by the payment-events queue.

Each SQS record carries a payment.created event. The consumer processes the
payment (validates funds, posts ledger entries, updates balances) and reports
per-message success or failure back to SQS via batchItemFailures.

Using batchItemFailures means a single failed message is retried without
re-processing the entire batch — important for idempotency under partial failures.
"""
import json
import logging
import uuid

from src.db import get_session
from src.services.payment_service import process_payment, InvalidTransitionError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event: dict, context) -> dict:
    """
    Lambda SQS trigger handler.
    Returns {"batchItemFailures": [...]} so only failed messages are retried.
    """
    failures = []

    for record in event.get("Records", []):
        message_id = record["messageId"]
        try:
            body = json.loads(record["body"])
            event_type = body.get("event_type")

            if event_type == "payment.created":
                _handle_payment_created(body["payment_id"])
            else:
                logger.warning("Unknown event type: %s — skipping", event_type)

        except InvalidTransitionError as exc:
            # Payment already processed — idempotent, not a real failure
            logger.info("Payment already processed (idempotent): %s", exc)
        except Exception as exc:
            logger.error("Failed to process SQS message %s: %s", message_id, exc, exc_info=True)
            failures.append({"itemIdentifier": message_id})

    return {"batchItemFailures": failures}


def _handle_payment_created(payment_id: str) -> None:
    db = get_session()
    try:
        pid = uuid.UUID(payment_id)
        payment = process_payment(db, payment_id=pid)
        db.commit()
        logger.info("Payment %s processed — status: %s", payment.id, payment.status)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
