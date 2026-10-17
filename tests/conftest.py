"""Pytest fixtures."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

# Env before app import
os.environ.setdefault(
    "SECRET_KEY",
    "test-secret-key-at-least-32-characters-long",
)
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from app.core.security import hash_password  # noqa: E402

os.environ["ADMIN_PASSWORD_HASH"] = hash_password("admin")

from app.config import get_settings  # noqa: E402
from app.db import init_db_for_tests  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture()
def client():
    get_settings.cache_clear()
    init_db_for_tests("sqlite:///:memory:")
    app = create_app()
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def auth_client(client: TestClient):
    r = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    assert r.status_code == 200
    csrf = r.json()["csrf_token"]
    client.headers.update({"X-CSRF-Token": csrf})
    return client
