import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from src.models.base import Base


class _NoCommitSession(Session):
    """Wraps a session so handler close()/commit()/rollback() calls are no-ops.
    The test fixture owns the transaction and controls rollback on teardown."""

    def close(self):
        self.expire_all()

    def commit(self):
        self.flush()

    def rollback(self):
        pass


_NoCommitSession._real_close = Session.close  # type: ignore[attr-defined]


@pytest.fixture(scope="session")
def db_engine():
    url = os.environ.get("TC_DB_URL")
    if url:
        engine = create_engine(url)
        Base.metadata.create_all(engine)
        yield engine
        engine.dispose()
    else:
        from testcontainers.postgres import PostgresContainer
        with PostgresContainer("postgres:16-alpine") as pg:
            engine = create_engine(pg.get_connection_url())
            Base.metadata.create_all(engine)
            yield engine
            engine.dispose()


@pytest.fixture
def db(db_engine):
    """Each test gets its own transaction, rolled back on exit."""
    connection = db_engine.connect()
    transaction = connection.begin()
    session = _NoCommitSession(bind=connection, expire_on_commit=False)
    yield session
    session._real_close()  # type: ignore[attr-defined]
    transaction.rollback()
    connection.close()
