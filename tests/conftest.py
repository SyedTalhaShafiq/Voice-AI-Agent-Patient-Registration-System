"""pytest configuration — provides an isolated DB per test."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import Base, engine


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    """Create all tables before tests, drop after."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(setup_db):
    """Provide a FastAPI TestClient for each test."""
    with TestClient(app) as c:
        yield c
