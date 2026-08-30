import os
import hashlib
import base64
import zipfile
import shutil
from cryptography.hazmat.primitives import hashes, serialization
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
    return base64.b64encode(hashlib.sha1(data).digest()).decode()


def _sha256_b64(data: bytes) -> str:
    return base64.b64encode(hashlib.sha256(data).digest()).decode()


def _build_manifest(entries: dict) -> bytes:
    lines = [
        "Manifest-Version: 1.0",
        "Created-By: 1.0 (FUDBot)",
        "",
    ]
    for name, digest in entries.items():
        lines.append(f"Name: {name}")
        lines.append(f"SHA-256-Digest: {digest}")
        lines.append("")
    return ("\r\n".join(lines) + "\r\n").encode("utf-8")


def _build_sf(manifest_bytes: bytes, entries: dict) -> bytes:
    mf_digest = _sha256_b64(manifest_bytes)
    lines = [
        "Signature-Version: 1.0",
        f"SHA-256-Digest-Manifest: {mf_digest}",
        "Created-By: 1.0 (FUDBot)",
        "",
    ]
    for name, digest in entries.items():
        section = f"Name: {name}\r\nSHA-256-Digest: {digest}\r\n\r\n".encode("utf-8")
        lines.append(f"Name: {name}")
        lines.append(f"SHA-256-Digest: {_sha256_b64(section)}")
        lines.append("")
    return ("\r\n".join(lines) + "\r\n").encode("utf-8")


def _build_pkcs7(sf_bytes: bytes, priv_key, cert) -> bytes:
    # PKCS7SignatureBuilder supports SHA256+ only — SHA1 not allowed
    builder = (
        PKCS7SignatureBuilder()
        .set_data(sf_bytes)
        .add_signer(cert, priv_key, hashes.SHA256())
    )
    return builder.sign(Encoding.DER, [])


def sign_apk(unsigned_apk: str, output_apk: str):
    priv_key, cert = _load_key_cert()

    entries = {}
    with zipfile.ZipFile(unsigned_apk, "r") as zf:
        for name in zf.namelist():
            if name.startswith("META-INF/"):
                continue
            entries[name] = _sha256_b64(zf.read(name))

    manifest_bytes = _build_manifest(entries)
    sf_bytes       = _build_sf(manifest_bytes, entries)
    pkcs7_bytes    = _build_pkcs7(sf_bytes, priv_key, cert)

    shutil.copy2(unsigned_apk, output_apk)
    with zipfile.ZipFile(output_apk, "a") as zf:
        zf.writestr(zipfile.ZipInfo("META-INF/MANIFEST.MF"), manifest_bytes)
        zf.writestr(zipfile.ZipInfo("META-INF/CERT.SF"),     sf_bytes)
        zf.writestr(zipfile.ZipInfo("META-INF/CERT.RSA"),    pkcs7_bytes)

    print(f"[✓] Signed APK → {output_apk}")
