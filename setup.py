"""
setup.py — Zero external tools. No Java. No apt. Pure Python only.
Keystore = PKCS12 via cryptography lib.
"""
import os
import subprocess
import stat
import urllib.request
from config import TOOLS_DIR, KEYSTORE_PATH, KEYSTORE_PASS, KEY_ALIAS


def _ensure_keystore():
    if os.path.exists(KEYSTORE_PATH):
        return
    os.makedirs(TOOLS_DIR, exist_ok=True)
    print("[*] Keystore generate ho rahi hai...")

    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import pkcs12
    import datetime

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME,             "FUD"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME,       "FUD"),
        x509.NameAttribute(NameOID.COUNTRY_NAME,            "US"),
    ])
    now = datetime.datetime.utcnow()
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject).issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=9125))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    p12 = pkcs12.serialize_key_and_certificates(
        name=KEY_ALIAS.encode(), key=key, cert=cert, cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(KEYSTORE_PASS.encode())
    )
    with open(KEYSTORE_PATH, "wb") as f:
        f.write(p12)
    print(f"[✓] Keystore ready → {KEYSTORE_PATH}")


def ensure_tools():
    os.makedirs(TOOLS_DIR, exist_ok=True)
    _ensure_keystore()
    print("[✓] All tools ready.")
