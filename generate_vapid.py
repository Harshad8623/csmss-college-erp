"""
Generate fresh VAPID keys in the exact format pywebpush 2.x expects.
Run: python generate_vapid.py
"""
from py_vapid import Vapid
from cryptography.hazmat.primitives.serialization import (
    Encoding, PublicFormat, PrivateFormat, NoEncryption
)
import base64

vapid = Vapid()
vapid.generate_keys()

# Public key as base64url (uncompressed point, no padding)
pub_bytes = vapid.public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
pub_b64url = base64.urlsafe_b64encode(pub_bytes).rstrip(b'=').decode()

# Private key as PEM string (single line with literal \n for env vars)
priv_pem = vapid.private_key.private_bytes(
    Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()
).decode().strip()

# Convert to single-line format safe for env vars
priv_single_line = priv_pem.replace('\n', '\\n')

print("=" * 60)
print("COPY THESE INTO .env AND RENDER ENVIRONMENT VARIABLES")
print("=" * 60)
print()
print(f"VAPID_PUBLIC_KEY={pub_b64url}")
print()
print(f"VAPID_PRIVATE_KEY={priv_single_line}")
print()
print("VAPID_CLAIMS_EMAIL=csmsserp@gmail.com")
print()
print("=" * 60)
print("ALSO — delete ALL push_subscriptions rows from DB so users")
print("re-subscribe with the new public key:")
print("  Run in Render shell or psql:")
print("  DELETE FROM push_subscriptions;")
print("=" * 60)
