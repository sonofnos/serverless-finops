# serverless-finops

Event-driven payment operations platform built on AWS serverless primitives.

**Stack:** Python 3.12 · Lambda · SQS FIFO · RDS PostgreSQL · AppSync (GraphQL) · React 19 · TypeScript · Vite

## Architecture

```
HTTP API Gateway
    │
    ├── POST /payments  ─→  PaymentsFunction (Lambda)
    │                          └── writes Payment + OutboxEvent (same transaction)
    │
    └── GET  /payments  ─→  PaymentsFunction (Lambda)

EventBridge (rate: 10s)
    └── OutboxPublisherFunction
            └── reads unpublished OutboxEvents (SKIP LOCKED)
            └── publishes to payment-events.fifo (SQS)

SQS FIFO + DLQ (max 3 retries)
    └── PaymentConsumerFunction
            └── locks accounts (ascending ID order → no deadlock)
            └── validates funds, posts double-entry LedgerEntries
            └── transitions Payment: PENDING → PROCESSING → COMPLETED/FAILED
            └── reports batchItemFailures (partial batch retry)

AppSync (GraphQL + WebSocket)
    └── Subscription.onPaymentStatusChanged
            └── pushes real-time status to connected React clients
```

## Key patterns

| Pattern | Where |
|---|---|
| Transactional Outbox | `payment_service.create_payment` + `outbox_publisher` |
| Idempotency key | `payments.idempotency_key` unique constraint |
| Deadlock-safe locking | ascending UUID sort before `SELECT … FOR UPDATE` |
| Double-entry ledger | DEBIT + CREDIT `LedgerEntry` per payment |
| Partial batch failure | `batchItemFailures` in SQS consumer |
| State machine | `Payment.can_transition_to()` |

## Running tests

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
PYTHONPATH=. pytest tests/ -v
```

Requires Docker (testcontainers spins up a real PostgreSQL instance).

In CI the `TC_DB_URL` env var bypasses testcontainers and uses the service container.

## Frontend

```bash
cd frontend-app
npm install
npm run dev   # http://localhost:5173
```

Set `.env.local`:
```
VITE_API_URL=https://<api-gateway-id>.execute-api.us-east-1.amazonaws.com
VITE_ACCOUNT_A=<uuid>
VITE_ACCOUNT_B=<uuid>
```

## Deploy

```bash
cd backend
sam build
sam deploy --guided
```
