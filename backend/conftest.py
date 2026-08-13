import os

# Test env vars must be set before app.config.get_settings() is first called
# by any import chain (db.py, security.py, etc.). This file lives at the repo
# root (not app/tests/) so pytest loads it as an ancestor conftest for every
# test package under app/ (rule_engine/tests, sources/tests, tds_detector/tests, ...).
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://nikhilbokaria@localhost:5432/karai_test")
os.environ.setdefault("JWT_SECRET", "test-only-secret-do-not-use-in-prod-abcdefghijklmnop")
os.environ.setdefault("ENCRYPTION_KEY", "test-only-encryption-key-do-not-use-in-prod")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.db import Base

get_settings.cache_clear()
settings = get_settings()

test_engine = create_engine(settings.database_url)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def _create_schema():
    import app.models  # noqa: F401 - register all models on Base.metadata

    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session():
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestSessionLocal(bind=connection)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
