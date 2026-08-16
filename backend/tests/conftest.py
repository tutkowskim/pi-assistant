import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "sqlite:///./data/test.db")
os.environ.setdefault("APP_DATA_DIR", "./data")
os.environ.setdefault("MODEL_IDS", "test-model-a,test-model-b,test-model-c,test-model-d")
os.environ.setdefault("DEFAULT_MODEL_ID", "test-model-a")
os.environ.setdefault("MODEL_DISCOVERY_ENABLED", "false")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")

from app.db.base import Base  # noqa: E402
from app.db.session import engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def clean_database():  # type: ignore[no-untyped-def]
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def client():  # type: ignore[no-untyped-def]
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_db():  # type: ignore[no-untyped-def]
    yield
    for suffix in ("", "-shm", "-wal"):
        Path(f"data/test.db{suffix}").unlink(missing_ok=True)
