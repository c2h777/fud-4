"""
signer.py — Proper Android v1 JAR signing.
Android v1 signing mein SHA-1 chahiye (SHA-256 nahi).
CERT.RSA = proper PKCS#7 CMS SignedData DER structure.
"""
import os
import hashlib
import base64
import zipfile
import shutil
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.padding import PKCS1v15
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.hazmat.primitives.serialization.pkcs7 import PKCS7SignatureBuilder
from cryptography.hazmat.primitives.serialization import Encoding
from config import KEYSTORE_PATH, KEYSTORE_PASS, KEY_ALIAS


def _load_key_cert():
    with open(KEYSTORE_PATH, "rb") as f:
        data = f.read()
    priv, cert, _ = pkcs12.load_key_and_certificates(
        data, KEYSTORE_PASS.encode()
    )
    return priv, cert


def _sha1_b64(data: bytes) -> str:
    """Android v1 signing = SHA-1 (not SHA-256)."""
    return base64.b64encode(hashlib.sha1(data).digest()).decode()


def _build_manifest(entries: dict) -> bytes:
    """
    MANIFEST.MF format — each entry = SHA1-Digest of raw file bytes.
    Line endings MUST be \\r\\n. Each section ends with blank line.
    Max line length 72 chars (continuation with space).
    """
    lines = [
        "Manifest-Version: 1.0",
        "Created-By: 1.0 (FUDBot)",
        "",
    ]
    for name, sha1 in entries.items():
        lines.append(f"Name: {name}")
        lines.append(f"SHA1-Digest: {sha1}")
        lines.append("")
    return ("\r\n".join(lines) + "\r\n").encode("utf-8")


def _build_sf(manifest_bytes: bytes, entries: dict) -> bytes:
    """
    CERT.SF — SHA1-Digest of each MANIFEST.MF section + whole manifest digest.
    """
    mf_sha1 = _sha1_b64(manifest_bytes)
    lines = [
        "Signature-Version: 1.0",
        f"SHA1-Digest-Manifest: {mf_sha1}",
        "Created-By: 1.0 (FUDBot)",
        "",
    ]
    # Each section digest — sha1 of the manifest entry block for that file
    for name, sha1 in entries.items():
        section = f"Name: {name}\r\nSHA1-Digest: {sha1}\r\n\r\n".encode("utf-8")
        lines.append(f"Name: {name}")
        lines.append(f"SHA1-Digest: {_sha1_b64(section)}")
        lines.append("")
    return ("\r\n".join(lines) + "\r\n").encode("utf-8")


def _build_pkcs7(sf_bytes: bytes, priv_key, cert) -> bytes:
    """PKCS#7 CMS SignedData — proper DER structure Android accepts."""
    builder = (
        PKCS7SignatureBuilder()
        .set_data(sf_bytes)
        .add_signer(cert, priv_key, hashes.SHA1())
    )
    # sign() with no options = detached=False? No — we need no detached
    # options=[] means no flags — content embedded
    return builder.sign(Encoding.DER, [])


def sign_apk(unsigned_apk: str, output_apk: str):
    priv_key, cert = _load_key_cert()

    # Collect all non-META-INF entries and their SHA1 digests
    entries = {}
    with zipfile.ZipFile(unsigned_apk, "r") as zf:
        for name in zf.namelist():
            if name.startswith("META-INF/"):
                continue
            entries[name] = _sha1_b64(zf.read(name))

    manifest_bytes = _build_manifest(entries)
    sf_bytes       = _build_sf(manifest_bytes, entries)
    pkcs7_bytes    = _build_pkcs7(sf_bytes, priv_key, cert)

    # Copy unsigned → output, then append META-INF
    shutil.copy2(unsigned_apk, output_apk)
    with zipfile.ZipFile(output_apk, "a") as zf:
        zf.writestr(
            zipfile.ZipInfo("META-INF/MANIFEST.MF"),
            manifest_bytes,
        )
        zf.writestr(
            zipfile.ZipInfo("META-INF/CERT.SF"),
            sf_bytes,
        )
        zf.writestr(
            zipfile.ZipInfo("META-INF/CERT.RSA"),
            pkcs7_bytes,
        )

    print(f"[✓] Signed APK → {output_apk}")
