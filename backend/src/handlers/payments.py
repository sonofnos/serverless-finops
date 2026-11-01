"""
Lambda handler: POST /payments  (initiate)
                GET  /payments/{id}
                GET  /payments?account_id=<uuid>
"""
import json
import uuid
from decimal import Decimal, InvalidOperation

from src.db import get_session
from src.services.payment_service import (
    create_payment,
    get_payment,
    list_payments,
    DuplicatePaymentError,
    AccountNotFoundError,
)
from src.handlers.response import ok, error


def _payment_to_dict(p) -> dict:
    return {
        "id": str(p.id),
        "idempotency_key": p.idempotency_key,
        "source_account_id": str(p.source_account_id),
        "dest_account_id": str(p.dest_account_id),
        "amount": str(p.amount),
        "currency": p.currency,
        "status": p.status.value,
        "failure_reason": p.failure_reason,
        "created_at": p.created_at.isoformat(),
        "updated_at": p.updated_at.isoformat(),
    }


def handler(event: dict, context) -> dict:
    method = event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method", "GET")
    path_params = event.get("pathParameters") or {}
    qs = event.get("queryStringParameters") or {}

    if method == "POST":
        return _create(event)

    if method == "GET" and path_params.get("id"):
        return _get(path_params["id"])

    if method == "GET":
        return _list(qs)

    return error("Method not allowed", 405)


def _create(event: dict) -> dict:
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return error("Invalid JSON body")

    required = {"idempotency_key", "source_account_id", "dest_account_id", "amount", "currency"}
    missing = required - body.keys()
    if missing:
        return error(f"Missing fields: {', '.join(sorted(missing))}")

    try:
        amount = Decimal(str(body["amount"]))
        if amount <= 0:
            return error("Amount must be positive")
    except InvalidOperation:
        return error("Invalid amount")

    try:
        src_id = uuid.UUID(body["source_account_id"])
        dst_id = uuid.UUID(body["dest_account_id"])
    except ValueError:
        return error("Invalid account UUID")

    db = get_session()
    try:
        payment = create_payment(
            db,
            idempotency_key=body["idempotency_key"],
            source_account_id=src_id,
            dest_account_id=dst_id,
            amount=amount,
            currency=body["currency"].upper(),
        )
        db.commit()
        return ok(_payment_to_dict(payment), status=201)
    except DuplicatePaymentError as exc:
        db.rollback()
        return ok(_payment_to_dict(exc.existing))  # idempotent 200
    except AccountNotFoundError as exc:
        db.rollback()
        return error(str(exc), 404)
    except Exception as exc:
        db.rollback()
        raise
    finally:
        db.close()


def _get(payment_id: str) -> dict:
    try:
        pid = uuid.UUID(payment_id)
    except ValueError:
        return error("Invalid payment UUID", 400)

    db = get_session()
    try:
        payment = get_payment(db, pid)
        if not payment:
            return error("Payment not found", 404)
        return ok(_payment_to_dict(payment))
    finally:
        db.close()


def _list(qs: dict) -> dict:
    account_id_str = qs.get("account_id")
    if not account_id_str:
        return error("account_id query parameter required")

    try:
        account_id = uuid.UUID(account_id_str)
    except ValueError:
        return error("Invalid account UUID")

    db = get_session()
    try:
        payments = list_payments(db, account_id)
        return ok({"payments": [_payment_to_dict(p) for p in payments]})
    finally:
        db.close()
