import uuid
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import select

from src.models import Account


def create_account(
    db: Session, *, owner_id: str, name: str, currency: str = "USD"
) -> Account:
    account = Account(owner_id=owner_id, name=name, currency=currency)
    db.add(account)
    db.flush()
    return account


def get_account(db: Session, account_id: uuid.UUID) -> Account | None:
    return db.scalar(select(Account).where(Account.id == account_id))


def credit_account(db: Session, *, account_id: uuid.UUID, amount: Decimal) -> Account:
    account = db.scalar(
        select(Account).where(Account.id == account_id).with_for_update()
    )
    if not account:
        raise ValueError(f"Account {account_id} not found")
    account.balance += amount
    db.flush()
    return account
