"""SQLAlchemy engine + session factory + the `get_db` dependency.

`get_db` yields a request-scoped session and closes it in a finally
block so request handlers can't leak connections.

`pool_pre_ping=True` adds a single `SELECT 1` round-trip per checkout
to catch connections silently killed by the database (idle timeouts,
restarts). Cheap insurance against intermittent "server closed the
connection unexpectedly" errors.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency — yields a Session, ensures it's closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
