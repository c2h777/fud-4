"""
setup.py — downloads JRE + apktool + Android build-tools once.
Pure Python ab tak ka rasta nahi chalta kyunki real APK modification
requires apktool (Java). Ye file sab kuch mirror ke through setup karti hai.
"""
import os
import io
import stat
import shutil
import zipfile
import urllib.request
from config import (
    TOOLS_DIR, KEYSTORE_PATH, KEYSTORE_PASS, KEY_ALIAS,
    JAVA_BIN, APKTOOL_JAR, APKSIGNER_BIN, ZIPALIGN_BIN, D8_BIN,
)

# ---- mirrors (offline-friendly ho to inhe apne mirror se replace karo) ----
JRE_URL       = "https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.10%2B7/OpenJDK17U-jre_x64_linux_hotspot_17.0.10_7.tar.gz"
APKTOOL_URL   = "https://github.com/iBotPeaches/Apktool/releases/download/v2.9.3/apktool_2.9.3.jar"
BUILDTOOLS_URL = "https://dl.google.com/android/repository/build-tools_r34-linux.zip"


def _download(url: str, dest: str):
    if os.path.exists(dest):
        return
    print(f"[*] downloading {url}")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    urllib.request.urlretrieve(url, dest)


def _extract_jre():
    jre_dir = os.path.join(TOOLS_DIR, "jre")
    if os.path.exists(JAVA_BIN):
        return
    import tarfile
    tarball = os.path.join(TOOLS_DIR, "jre.tgz")
    _download(JRE_URL, tarball)
    with tarfile.open(tarball) as t:
        t.extractall(TOOLS_DIR)
    # tarball root looks like jdk-17.0.10+7-jre/
    for d in os.listdir(TOOLS_DIR):
        if d.startswith("jdk-") or d.startswith("OpenJDK"):
            os.rename(os.path.join(TOOLS_DIR, d), jre_dir)
            break
    os.remove(tarball)


def _extract_build_tools():
    bt_dir = os.path.join(TOOLS_DIR, "build-tools")
    if os.path.exists(APKSIGNER_BIN):
        return
    zpath = os.path.join(TOOLS_DIR, "bt.zip")
    _download(BUILDTOOLS_URL, zpath)
    with zipfile.ZipFile(zpath) as z:
        z.extractall(TOOLS_DIR)
    # extracted as android-XX/ — move to build-tools/
    for d in os.listdir(TOOLS_DIR):
        if d.startswith("android-"):
            os.rename(os.path.join(TOOLS_DIR, d), bt_dir)
            break
    os.remove(zpath)
    for b in (APKSIGNER_BIN, ZIPALIGN_BIN, D8_BIN):
        if os.path.exists(b):
            os.chmod(b, os.stat(b).st_mode | stat.S_IEXEC)


def _ensure_keystore():
    if os.path.exists(KEYSTORE_PATH):
        return
    os.makedirs(TOOLS_DIR, exist_ok=True)
    print("[*] keystore generating...")

    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import pkcs12
    import datetime

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME,       "System"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "System"),
        x509.NameAttribute(NameOID.COUNTRY_NAME,      "US"),
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
    print(f"[✓] keystore ready")


def ensure_tools():
    os.makedirs(TOOLS_DIR, exist_ok=True)
    _extract_jre()
    _download(APKTOOL_URL, APKTOOL_JAR)
    _extract_build_tools()
    _ensure_keystore()
    print("[✓] tools ready")
