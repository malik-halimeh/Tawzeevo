"""Envelope encryption for tenant backups (PHASE_04.md L; D-057).

One master key per environment (the KEK, a hosting secret) wraps a random 256-bit data key per
tenant (the DEK). Backup payloads are AES-256-GCM encrypted with the DEK; the manifest core is
bound as associated data so a manifest swapped between backups fails to decrypt. Plaintext keys
exist only in process memory.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
from typing import Any
from uuid import UUID

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from tawzeevo_api.errors import AppError

FORMAT_VERSION = 1
NONCE_BYTES = 12
KEY_BYTES = 32


class BackupIntegrityError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(409, "BACKUP_INTEGRITY_FAILED", message)


def load_master_key(encoded: str | None) -> bytes:
    """Decode the environment master key (base64 of 32 random bytes)."""
    if not encoded:
        raise AppError(503, "BACKUP_KEY_UNAVAILABLE", "Backup master key is not configured")
    try:
        key = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise AppError(503, "BACKUP_KEY_INVALID", "Backup master key is not valid") from exc
    if len(key) != KEY_BYTES:
        raise AppError(503, "BACKUP_KEY_INVALID", "Backup master key must be 32 bytes")
    return key


def generate_key() -> bytes:
    return os.urandom(KEY_BYTES)


def _seal(key: bytes, plaintext: bytes, associated: bytes) -> bytes:
    nonce = os.urandom(NONCE_BYTES)
    sealed = AESGCM(key).encrypt(nonce, plaintext, associated)
    return bytes([FORMAT_VERSION]) + nonce + sealed


def _open(key: bytes, blob: bytes, associated: bytes) -> bytes:
    if len(blob) < 1 + NONCE_BYTES + 16 or blob[0] != FORMAT_VERSION:
        raise BackupIntegrityError("Backup format is not recognised")
    nonce, sealed = blob[1 : 1 + NONCE_BYTES], blob[1 + NONCE_BYTES :]
    try:
        return AESGCM(key).decrypt(nonce, sealed, associated)
    except InvalidTag as exc:
        raise BackupIntegrityError(
            "Backup could not be authenticated (tampered or wrong key)"
        ) from exc


def wrap_key(master_key: bytes, data_key: bytes, tenant_id: UUID, key_id: UUID) -> bytes:
    return _seal(master_key, data_key, f"dek:{tenant_id}:{key_id}".encode())


def unwrap_key(master_key: bytes, wrapped: bytes, tenant_id: UUID, key_id: UUID) -> bytes:
    return _open(master_key, wrapped, f"dek:{tenant_id}:{key_id}".encode())


def wrap_secret(master_key: bytes, secret: str, tenant_id: UUID, purpose: str) -> bytes:
    return _seal(master_key, secret.encode("utf-8"), f"{purpose}:{tenant_id}".encode())


def unwrap_secret(master_key: bytes, wrapped: bytes, tenant_id: UUID, purpose: str) -> str:
    return _open(master_key, wrapped, f"{purpose}:{tenant_id}".encode()).decode("utf-8")


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def encrypt_payload(data_key: bytes, payload: bytes, manifest_core: dict[str, Any]) -> bytes:
    """Encrypt the export; the manifest core is authenticated but stored in clear."""
    return _seal(data_key, payload, canonical_json(manifest_core))


def decrypt_payload(data_key: bytes, blob: bytes, manifest_core: dict[str, Any]) -> bytes:
    return _open(data_key, blob, canonical_json(manifest_core))


def checksum(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()
