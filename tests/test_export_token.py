"""Token encryption and Google error mapping."""

from app.core.errors import AppError
from app.export.errors import raise_google_error
from app.export.token_store import decrypt_token, encrypt_token


def test_encrypt_roundtrip(monkeypatch):
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode()
    monkeypatch.setenv("GOOGLE_TOKEN_ENCRYPTION_KEY", key)
    from app.config import get_settings

    get_settings.cache_clear()
    blob = encrypt_token("refresh-token-value")
    assert decrypt_token(blob) == "refresh-token-value"


def test_invalid_grant_mapping():
    class FakeExc(Exception):
        content = b'{"error": "invalid_grant"}'

    try:
        raise_google_error(FakeExc())
        assert False, "should raise"
    except AppError as exc:
        assert exc.code == "google_reauth_required"
