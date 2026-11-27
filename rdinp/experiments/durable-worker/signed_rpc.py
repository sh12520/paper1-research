"""HMAC-authenticated messages for the bilateral development transport.

The transport permits an authenticated retry. The durable task store owns
operation idempotence and admission state.
"""

import hmac
import json
import re
import secrets


_VERSION = 1
_FIELDS = {"version", "nonce", "payload", "tag"}
_NONCE = re.compile(r"[A-Za-z0-9_-]{1,128}")
_TAG = re.compile(r"[0-9a-f]{64}")


def _object_without_duplicates(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("duplicate JSON key")
        obj[key] = value
    return obj


def _canonical_json(value) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True, allow_nan=False).encode("ascii")
    except (TypeError, ValueError, RecursionError) as exc:
        raise ValueError("message must contain finite JSON data") from exc


def _validate_scope(route: str, nonce: str) -> None:
    if not isinstance(route, str) or not route.startswith("/") or any(
        not 0x21 <= ord(ch) <= 0x7E for ch in route
    ):
        raise ValueError("invalid HTTP route")
    if not isinstance(nonce, str) or _NONCE.fullmatch(nonce) is None:
        raise ValueError("invalid request nonce")


class Authenticator:
    """Bind each request and its reply to one route and request nonce."""

    def __init__(self, key: bytes):
        if not isinstance(key, bytes) or len(key) < 32:
            raise ValueError("authentication key must contain at least 32 bytes")
        self._key = key

    def _tag(self, direction: str, route: str, nonce: str, payload: dict) -> str:
        # A protocol identifier separates these MACs from any other use of the key.
        body = _canonical_json(["rdinp-worker-rpc", _VERSION, direction, route, nonce, payload])
        return hmac.digest(self._key, body, "sha256").hex()

    def _pack(self, direction: str, route: str, nonce: str, payload: dict) -> bytes:
        _validate_scope(route, nonce)
        if not isinstance(payload, dict):
            raise ValueError("message payload must be a JSON object")
        return _canonical_json({
            "version": _VERSION,
            "nonce": nonce,
            "payload": payload,
            "tag": self._tag(direction, route, nonce, payload),
        })

    def _unpack(self, direction: str, route: str, raw: bytes) -> tuple[str, dict]:
        if not isinstance(raw, bytes):
            raise ValueError("message must be UTF-8 bytes")
        try:
            envelope = json.loads(raw.decode("utf-8"), object_pairs_hook=_object_without_duplicates)
        except (ValueError, RecursionError) as exc:
            raise ValueError("malformed message envelope") from exc
        if not isinstance(envelope, dict) or envelope.keys() != _FIELDS:
            raise ValueError("malformed message envelope")
        if type(envelope["version"]) is not int or envelope["version"] != _VERSION:
            raise ValueError("unsupported message version")
        nonce, payload, tag = envelope["nonce"], envelope["payload"], envelope["tag"]
        _validate_scope(route, nonce)
        if not isinstance(payload, dict) or not isinstance(tag, str) or _TAG.fullmatch(tag) is None:
            raise ValueError("malformed authenticated payload")
        expected = self._tag(direction, route, nonce, payload)
        if not hmac.compare_digest(expected, tag):
            raise ValueError("message authentication failed")
        return nonce, payload

    def pack_request(self, route: str, payload: dict, nonce: str | None = None) -> tuple[str, bytes]:
        nonce = secrets.token_hex(16) if nonce is None else nonce
        return nonce, self._pack("request", route, nonce, payload)

    def unpack_request(self, route: str, raw: bytes) -> tuple[str, dict]:
        return self._unpack("request", route, raw)

    def pack_reply(self, route: str, nonce: str, payload: dict) -> bytes:
        return self._pack("reply", route, nonce, payload)

    def unpack_reply(self, route: str, nonce: str, raw: bytes) -> dict:
        _validate_scope(route, nonce)
        returned_nonce, payload = self._unpack("reply", route, raw)
        if returned_nonce != nonce:
            raise ValueError("reply nonce does not match request")
        return payload
