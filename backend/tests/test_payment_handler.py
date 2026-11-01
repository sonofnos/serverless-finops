"""
Unit tests for the payments Lambda handler.
Uses the real DB session (via conftest fixture) — no mocking of the DB layer.
"""
import json
import uuid
from decimal import Decimal
import pytest

from src.services.account_service import create_account
from src.db import get_session as _orig_get_session


def _event(method: str, body=None, path_params=None, qs=None) -> dict:
    return {
        "httpMethod": method,
        "body": json.dumps(body) if body else None,
        "pathParameters": path_params or {},
        "queryStringParameters": qs or {},
    }


@pytest.fixture(autouse=True)
def patch_db(db, monkeypatch):
    """Route get_session() to the test-scoped session."""
    monkeypatch.setattr("src.handlers.payments.get_session", lambda: db)


@pytest.fixture
def accounts(db):
    a = create_account(db, owner_id="user-a", name="Alice")
    b = create_account(db, owner_id="user-b", name="Bob")
    a.balance = Decimal("500.00")
    db.flush()
    return a, b


class TestCreatePaymentHandler:
    def test_201_on_valid_request(self, accounts):
        from src.handlers.payments import handler
        a, b = accounts
        resp = handler(_event("POST", {
            "idempotency_key": "h-001",
            "source_account_id": str(a.id),
            "dest_account_id": str(b.id),
            "amount": "100.00",
            "currency": "USD",
        }), None)
        assert resp["statusCode"] == 201
        body = json.loads(resp["body"])
        assert body["status"] == "PENDING"

    def test_idempotent_200_on_duplicate_key(self, accounts):
        from src.handlers.payments import handler
        a, b = accounts
        evt = _event("POST", {
            "idempotency_key": "h-idem",
            "source_account_id": str(a.id),
            "dest_account_id": str(b.id),
            "amount": "50.00",
            "currency": "USD",
        })
        r1 = handler(evt, None)
        r2 = handler(evt, None)
        assert r1["statusCode"] == 201
        assert r2["statusCode"] == 200
        assert json.loads(r1["body"])["id"] == json.loads(r2["body"])["id"]

    def test_400_on_missing_fields(self):
        from src.handlers.payments import handler
        resp = handler(_event("POST", {"idempotency_key": "only-key"}), None)
        assert resp["statusCode"] == 400

    def test_404_on_unknown_account(self):
        from src.handlers.payments import handler
        resp = handler(_event("POST", {
            "idempotency_key": "h-404",
            "source_account_id": str(uuid.uuid4()),
            "dest_account_id": str(uuid.uuid4()),
            "amount": "10.00",
            "currency": "USD",
        }), None)
        assert resp["statusCode"] == 404

    def test_get_payment_by_id(self, accounts):
        from src.handlers.payments import handler
        a, b = accounts
        create_resp = handler(_event("POST", {
            "idempotency_key": "h-get",
            "source_account_id": str(a.id),
            "dest_account_id": str(b.id),
            "amount": "30.00",
            "currency": "USD",
        }), None)
        pid = json.loads(create_resp["body"])["id"]
        get_resp = handler(_event("GET", path_params={"id": pid}), None)
        assert get_resp["statusCode"] == 200
        assert json.loads(get_resp["body"])["id"] == pid

    def test_list_payments_by_account(self, accounts):
        from src.handlers.payments import handler
        a, b = accounts
        for i in range(3):
            handler(_event("POST", {
                "idempotency_key": f"list-{i}",
                "source_account_id": str(a.id),
                "dest_account_id": str(b.id),
                "amount": "10.00",
                "currency": "USD",
            }), None)
        resp = handler(_event("GET", qs={"account_id": str(a.id)}), None)
        assert resp["statusCode"] == 200
        assert len(json.loads(resp["body"])["payments"]) == 3
