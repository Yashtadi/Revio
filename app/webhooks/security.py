import hashlib
import hmac


def verify_signature(payload_body: bytes, signature_header: str, secret: str) -> bool:
    """Return True only if signature_header matches an HMAC-SHA256 of the body."""
    if not signature_header:
        return False

    expected = (
        "sha256="
        + hmac.new(
            key=secret.encode(),
            msg=payload_body,
            digestmod=hashlib.sha256,
        ).hexdigest()
    )

    return hmac.compare_digest(expected, signature_header)
