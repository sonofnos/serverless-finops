"""
Outbox Publisher Lambda — triggered on a schedule (EventBridge every 10s).

Reads unpublished OutboxEvent rows, publishes them to SQS, and marks them
published. The transactional outbox pattern guarantees every business event
reaches SQS at least once, even if a Lambda crashed between writing the DB
row and sending the SQS message.
"""
import json
import logging
import os

import boto3
from sqlalchemy import select

from src.db import get_session
from src.models import OutboxEvent

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_sqs = None


def _get_sqs():
    global _sqs
    if _sqs is None:
        _sqs = boto3.client("sqs", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    return _sqs


def handler(event: dict, context) -> None:
    queue_url = os.environ["PAYMENT_QUEUE_URL"]
    db = get_session()
    try:
        unpublished = list(
            db.scalars(
                select(OutboxEvent)
                .where(OutboxEvent.published == False)  # noqa: E712
                .order_by(OutboxEvent.created_at)
                .limit(100)
                .with_for_update(skip_locked=True)
            )
        )

        if not unpublished:
            return

        sqs = _get_sqs()
        for evt in unpublished:
            payload = json.loads(evt.payload)
            response = sqs.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps({"event_type": evt.event_type, **payload}),
                MessageGroupId=payload.get("payment_id", str(evt.id)),
            )
            evt.published = True
            evt.sqs_message_id = response["MessageId"]

        db.commit()
        logger.info("Published %d outbox events to SQS", len(unpublished))
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
