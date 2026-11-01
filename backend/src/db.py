import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from src.models.base import Base

_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        url = os.environ["DATABASE_URL"]
        # RDS connections from Lambda are short-lived; pool_pre_ping re-validates
        # stale connections that sat idle while the function was cold.
        _engine = create_engine(url, pool_pre_ping=True, pool_size=2, max_overflow=0)
    return _engine


def get_session() -> Session:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _SessionLocal()


def create_tables():
    Base.metadata.create_all(get_engine())
