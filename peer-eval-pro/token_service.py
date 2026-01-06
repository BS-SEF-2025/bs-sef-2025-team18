import base64
import json
import hmac
import hashlib
import time
from typing import Dict, Any

SECRET_KEY = "CHANGE_ME_TO_SOMETHING_RANDOM"


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("utf-8"))


def _sign(msg: bytes) -> str:
    sig = hmac.new(SECRET_KEY.encode("utf-8"), msg, hashlib.sha256).digest()
    return _b64url_encode(sig)


def create_access_token(username: str, role: str, expires_minutes: int = 60) -> str:
    header = {"alg": "HS256", "typ": "TOKEN"}
    payload = {
        "sub": username,
        "role": role,
        "exp": int(time.time()) + expires_minutes * 60,
    }

    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))

    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    signature = _sign(signing_input)

    return f"{header_b64}.{payload_b64}.{signature}"


def decode_access_token(token: str) -> Dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid token format")

    header_b64, payload_b64, signature = parts
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")

    expected_sig = _sign(signing_input)
    if not hmac.compare_digest(signature, expected_sig):
        raise ValueError("Invalid token signature")

    payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    if int(payload.get("exp", 0)) < int(time.time()):
        raise ValueError("Token expired")

    return payload
