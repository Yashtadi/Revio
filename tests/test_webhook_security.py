import hashlib
import hmac

from app.webhooks.security import verify_signature


def _sign(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_valid_signature_is_accepted():
    body = b'{"hello": "world"}'
    secret = "topsecret"
    assert verify_signature(body, _sign(body, secret), secret) is True


def test_wrong_signature_is_rejected():
    assert verify_signature(b"{}", "sha256=deadbeef", "topsecret") is False


def test_missing_signature_is_rejected():
    assert verify_signature(b"{}", "", "topsecret") is False
