"""Closed permit-v1 envelopes over the frozen C2 detached-JWS carrier."""

from pathlib import Path
import struct
import sys
from uuid import uuid4

from cryptography.hazmat.primitives import serialization
from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "c2"))
from contracts import jcs, parse, sha
from crypto import Identity, Trust
sys.path.pop(0)

REVISION = "RDINP-REUSABLE-PERMIT-1"
AUTHORITY = "edge-authority"
MAX_HEADER = 32 * 1024
MAX_DATA = 2 * 1024 * 1024
MAX_FRAME = 4 + MAX_HEADER + MAX_DATA

SCHEMA = parse((HERE / "permit.schema.json").read_bytes())
ENVELOPE = Draft202012Validator(SCHEMA)
BODIES = {
    name: Draft202012Validator({"$defs": SCHEMA["$defs"], "$ref": f"#/$defs/{name}"})
    for name in SCHEMA["properties"]["kind"]["enum"]
}


class ProtocolShape:
    """Trust.verify calls message() before checking the ES256 signature."""

    @staticmethod
    def message(message):
        ENVELOPE.validate(message)
        BODIES[message["kind"]].validate(message["body"])


def load_identity(principal, encoded_key):
    role = "responder" if principal == AUTHORITY else "initiator"
    key = serialization.load_pem_private_key(encoded_key.encode("ascii"), password=None)
    return Identity(principal, role, key)


def key_pem(identity):
    return identity.key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode("ascii")


class Codec:
    def __init__(self, identity, trust):
        self.identity = identity
        self.trust = trust

    def sign(self, kind, body, recipient, correlation="", payload=b""):
        return self.identity.sign({
            "revision": REVISION,
            "kind": kind,
            "sender": self.identity.principal,
            "recipient": recipient,
            "nonce": uuid4().hex,
            "correlation": correlation,
            "payload_sha256": sha(payload),
            "body": body,
        })

    def verify(self, raw, sender, recipient, payload=b""):
        role = "responder" if sender == AUTHORITY else "initiator"
        message = self.trust.verify(raw, ProtocolShape, sender, role)
        if message["recipient"] != recipient or message["payload_sha256"] != sha(payload):
            raise ValueError("wrong audience or payload binding")
        return message


def frame(header, payload=b""):
    if not 0 < len(header) <= MAX_HEADER or len(payload) > MAX_DATA:
        raise ValueError("frame size")
    return struct.pack("!I", len(header)) + header + payload


def unframe(contents):
    if not 4 < len(contents) <= MAX_FRAME:
        raise ValueError("frame size")
    (length,) = struct.unpack("!I", contents[:4])
    if not 0 < length <= MAX_HEADER or length > len(contents) - 4:
        raise ValueError("invalid frame header size")
    header, payload = contents[4:4 + length], contents[4 + length:]
    if len(payload) > MAX_DATA:
        raise ValueError("payload size")
    return header, payload
