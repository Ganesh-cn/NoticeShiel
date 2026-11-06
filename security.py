"""
NoticeShield - Cryptographic Security Module
Implements Ed25519 digital signatures, canonical structured JSON serialization,
and SHA-256 hashing for official notice integrity.
"""

import os
import json
import base64
import uuid
import hashlib
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

KEYS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'keys')
PRIVATE_KEY_PATH = os.path.join(KEYS_DIR, 'ed25519_private.pem')
PUBLIC_KEY_PATH = os.path.join(KEYS_DIR, 'ed25519_public.pem')

def ensure_keys_exist():
    """
    Checks if Ed25519 keypair exists in keys/ directory.
    If not, generates a new Ed25519 key pair and saves them to PEM files.
    The private key stays strictly on the backend.
    """
    os.makedirs(KEYS_DIR, exist_ok=True)

    if not os.path.exists(PRIVATE_KEY_PATH) or not os.path.exists(PUBLIC_KEY_PATH):
        # Generate new Ed25519 private key
        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()

        # Serialize and write private key
        pem_private = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        with open(PRIVATE_KEY_PATH, 'wb') as f:
            f.write(pem_private)

        # Serialize and write public key
        pem_public = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        with open(PUBLIC_KEY_PATH, 'wb') as f:
            f.write(pem_public)

def load_private_key() -> ed25519.Ed25519PrivateKey:
    """Loads backend Ed25519 private key from PEM file."""
    ensure_keys_exist()
    with open(PRIVATE_KEY_PATH, 'rb') as f:
        return serialization.load_pem_private_key(f.read(), password=None)

def load_public_key() -> ed25519.Ed25519PublicKey:
    """Loads trusted Ed25519 public key from PEM file."""
    ensure_keys_exist()
    with open(PUBLIC_KEY_PATH, 'rb') as f:
        return serialization.load_pem_public_key(f.read())

def get_public_key_pem_str() -> str:
    """Returns the PEM-encoded public key string for verification transparency."""
    ensure_keys_exist()
    with open(PUBLIC_KEY_PATH, 'r') as f:
        return f.read()

def canonicalize_notice_data(data: dict) -> str:
    """
    Produces canonical deterministic JSON string from notice fields.
    Ensures sorted keys, UTF-8 compatibility, and no whitespace variance.
    Keys signed: notice_id, title, department, notice_date, event_date, venue, description, issuer.
    """
    canonical_dict = {
        'department': str(data.get('department', '')).strip(),
        'description': str(data.get('description', '')).strip(),
        'event_date': str(data.get('event_date', '')).strip(),
        'issuer': str(data.get('issuer', '')).strip(),
        'notice_date': str(data.get('notice_date', '')).strip(),
        'notice_id': str(data.get('notice_id', '')).strip(),
        'title': str(data.get('title', '')).strip(),
        'venue': str(data.get('venue', '')).strip()
    }
    return json.dumps(canonical_dict, sort_keys=True, separators=(',', ':'))

def sign_canonical_data(canonical_json: str) -> str:
    """
    Signs canonical JSON bytes with backend Ed25519 private key.
    Returns Base64-encoded signature string.
    """
    private_key = load_private_key()
    signature_bytes = private_key.sign(canonical_json.encode('utf-8'))
    return base64.b64encode(signature_bytes).decode('utf-8')

def verify_ed25519_signature(canonical_json: str, signature_b64: str) -> bool:
    """
    Verifies that the canonical JSON was signed by the official private key
    using the official Ed25519 public key.
    Returns True if authentic, False otherwise.
    """
    try:
        public_key = load_public_key()
        sig_bytes = base64.b64decode(signature_b64.encode('utf-8'))
        public_key.verify(sig_bytes, canonical_json.encode('utf-8'))
        return True
    except Exception:
        return False

def compute_sha256(content: str) -> str:
    """Computes standard SHA-256 hex digest of a string."""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

def generate_notice_id() -> str:
    """Generates a clean, unique Notice ID, e.g., 'NS-2026-A8B9C0D1'."""
    suffix = uuid.uuid4().hex[:8].upper()
    return f"NS-2026-{suffix}"
