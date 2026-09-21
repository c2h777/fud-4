"""Auto-download + 4096-bit Play-style keystore."""
import os
import shutil
import stat
import tarfile
import threading
import urllib.request
import zipfile
from config import (
    TOOLS_DIR, KEYSTORE_PATH, KEYSTORE_PASS, KEY_ALIAS,
    JAVA_BIN, ECJ_JAR, APKTOOL_JAR, BT_DIR,
    APKSIGNER_BIN, ZIPALIGN_BIN, D8_BIN, ANDROID_JAR,
    URL_JRE, URL_ECJ, URL_APKTOOL, URL_BUILDTOOLS,
)

PLATFORM_JAR_URLS = [
    "https://raw.githubusercontent.com/Sable/android-platforms/master/android-30/android.jar",
    "https://github.com/Sable/android-platforms/raw/master/android-30/android.jar",
]

_READY_FLAG = os.path.join(TOOLS_DIR, ".ready_v3")
_setup_lock = threading.Lock()
_setup_done = threading.Event()
_setup_error = {"exc": None}


def _download(url, dest):
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        print(f"[i] {os.path.basename(dest)} present", flush=True)
        return
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    print(f"[*] downloading {os.path.basename(dest)}", flush=True)
    tmp = dest + ".part"
    urllib.request.urlretrieve(url, tmp)
    os.replace(tmp, dest)
    print(f"[✓] {os.path.basename(dest)} {os.path.getsize(dest)} bytes", flush=True)


def _extract_jre():
    if os.path.exists(JAVA_BIN):
        return
    tgz = os.path.join(TOOLS_DIR, "jre.tgz")
    _download(URL_JRE, tgz)
    print("[*] extracting jre ...", flush=True)
    with tarfile.open(tgz) as t:
        try:
            t.extractall(TOOLS_DIR, filter="fully_trusted")
        except TypeError:
            t.extractall(TOOLS_DIR)
    picked = None
    for d in sorted(os.listdir(TOOLS_DIR)):
        full = os.path.join(TOOLS_DIR, d)
        if not os.path.isdir(full) or d == "jre":
            continue
        if ("jdk-" in d) or d.lower().startswith("jre"):
            if os.path.exists(os.path.join(full, "bin", "java")):
                picked = full
                break
    if not picked:
        raise RuntimeError("jre extract failed")
    target = os.path.join(TOOLS_DIR, "jre")
    if os.path.exists(target):
        shutil.rmtree(target)
    os.rename(picked, target)
    if os.path.exists(tgz):
        os.remove(tgz)


def _extract_build_tools():
    if os.path.exists(APKSIGNER_BIN):
        return
    zpath = os.path.join(TOOLS_DIR, "bt.zip")
    _download(URL_BUILDTOOLS, zpath)
    print("[*] extracting build-tools ...", flush=True)
    with zipfile.ZipFile(zpath) as z:
        z.extractall(TOOLS_DIR)
    picked = None
    for d in sorted(os.listdir(TOOLS_DIR)):
        full = os.path.join(TOOLS_DIR, d)
        if os.path.isdir(full) and d.startswith("android-"):
            if os.path.exists(os.path.join(full, "apksigner")):
                picked = full
                break
    if not picked:
        raise RuntimeError("build-tools extract failed")
    if os.path.exists(BT_DIR):
        shutil.rmtree(BT_DIR)
    os.rename(picked, BT_DIR)
    if os.path.exists(zpath):
        os.remove(zpath)
    for b in (APKSIGNER_BIN, ZIPALIGN_BIN, D8_BIN):
        if os.path.exists(b):
            os.chmod(b, os.stat(b).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def _extract_platform():
    if os.path.exists(ANDROID_JAR) and os.path.getsize(ANDROID_JAR) > 0:
        return
    os.makedirs(os.path.dirname(ANDROID_JAR), exist_ok=True)
    for jar_url in PLATFORM_JAR_URLS:
        try:
            print(f"[*] trying {jar_url}", flush=True)
            tmp = ANDROID_JAR + ".part"
            urllib.request.urlretrieve(jar_url, tmp)
            if os.path.getsize(tmp) > 1024 * 100:
                os.replace(tmp, ANDROID_JAR)
                return
            os.remove(tmp)
        except Exception as e:
            print(f"[!] failed: {e}", flush=True)
    raise RuntimeError("android.jar unavailable")


def _ensure_keystore():
    """4096-bit RSA + Google-like cert fields."""
    if os.path.exists(KEYSTORE_PATH):
        return
    os.makedirs(TOOLS_DIR, exist_ok=True)
    print("[*] generating 4096-bit play keystore ...", flush=True)
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import pkcs12
    import datetime

    key = rsa.generate_private_key(public_exponent=65537, key_size=4096)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME,             "US"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME,   "California"),
        x509.NameAttribute(NameOID.LOCALITY_NAME,            "Mountain View"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME,        "Google Inc."),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "Android"),
        x509.NameAttribute(NameOID.COMMON_NAME,              "Android"),
    ])
    now = datetime.datetime.utcnow()
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject).issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=10950))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.KeyUsage(
            digital_signature=True, content_commitment=False,
            key_encipherment=False, data_encipherment=False,
            key_agreement=False, key_cert_sign=False, crl_sign=False,
            encipher_only=False, decipher_only=False,
        ), critical=True)
        .sign(key, hashes.SHA384())
    )
    p12 = pkcs12.serialize_key_and_certificates(
        name=KEY_ALIAS.encode(), key=key, cert=cert, cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(KEYSTORE_PASS.encode()),
    )
    with open(KEYSTORE_PATH, "wb") as f:
        f.write(p12)
    print("[✓] 4096-bit play keystore ready", flush=True)


def _do_setup():
    _extract_jre()
    _download(URL_ECJ, ECJ_JAR)
    _download(URL_APKTOOL, APKTOOL_JAR)
    _extract_build_tools()
    _extract_platform()
    _ensure_keystore()
    with open(_READY_FLAG, "w") as f:
        f.write("ok")
    print("[✓] ALL TOOLS READY", flush=True)


def ensure_tools():
    if os.path.exists(_READY_FLAG):
        _setup_done.set()
        return
    with _setup_lock:
        if os.path.exists(_READY_FLAG):
            _setup_done.set()
            return
        try:
            _do_setup()
            _setup_error["exc"] = None
        except Exception as e:
            _setup_error["exc"] = e
            print(f"[!] setup failed: {e}", flush=True)
            raise
        finally:
            _setup_done.set()


def wait_ready(timeout: float = 900.0) -> bool:
    if os.path.exists(_READY_FLAG):
        return True
    ok = _setup_done.wait(timeout)
    if _setup_error["exc"]:
        raise _setup_error["exc"]
    return ok and os.path.exists(_READY_FLAG)
