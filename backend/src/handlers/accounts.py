"""
Lambda handler: POST /accounts
                GET  /accounts/{id}
"""
import json
import uuid

from src.db import get_session
from src.services.account_service import create_account, get_account, credit_account
from src.handlers.response import ok, error


def _account_to_dict(a) -> dict:
    return {
        "id": str(a.id),
        "owner_id": a.owner_id,
        "name": a.name,
        "currency": a.currency,
        "balance": str(a.balance),
        "created_at": a.created_at.isoformat(),
    }


def handler(event: dict, context) -> dict:
    method = event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method", "GET")
    path_params = event.get("pathParameters") or {}

    if method == "POST":
        return _create(event)
    if method == "GET" and path_params.get("id"):
        return _get(path_params["id"])
    return error("Method not allowed", 405)


def _create(event: dict) -> dict:
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return error("Invalid JSON body")

    missing = {"owner_id", "name"} - body.keys()
    if missing:
        return error(f"Missing fields: {', '.join(sorted(missing))}")

    db = get_session()
    try:
        account = create_account(
            db,
            owner_id=body["owner_id"],
            name=body["name"],
            currency=body.get("currency", "USD").upper(),
        )
        db.commit()
        return ok(_account_to_dict(account), status=201)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _get(account_id: str) -> dict:
    try:
        aid = uuid.UUID(account_id)
    except ValueError:
        return error("Invalid account UUID", 400)

    db = get_session()
    try:
        account = get_account(db, aid)
        if not account:
            return error("Account not found", 404)
        return ok(_account_to_dict(account))
    finally:
        db.close()
