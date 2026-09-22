"""Tools auto-download. Pulls real API 34 platform for android.jar."""
import os
import shutil
import stat
import tarfile
import threading
import urllib.request
import zipfile

from config import (
    TOOLS_DIR, JAVA_BIN, JAVAC_BIN, D8_BIN, APKTOOL_JAR, BT_DIR,
    APKSIGNER_BIN, ZIPALIGN_BIN, AAPT2_BIN, ANDROID_JAR,
    URL_JRE, URL_APKTOOL, URL_BUILDTOOLS, URL_ANDROID_PLATFORM,
)

_READY_FLAG = os.path.join(TOOLS_DIR, ".ready_v8")

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


def _extract_jdk():
    if os.path.exists(JAVA_BIN) and os.path.exists(JAVAC_BIN):
        return
    tgz = os.path.join(TOOLS_DIR, "jdk.tgz")
    _download(URL_JRE, tgz)
    with tarfile.open(tgz) as t:
        try:
            t.extractall(TOOLS_DIR, filter="fully_trusted")
        except TypeError:
            t.extractall(TOOLS_DIR)
    picked = None
    for d in sorted(os.listdir(TOOLS_DIR)):
        full = os.path.join(TOOLS_DIR, d)
        if not os.path.isdir(full) or d in ("jre", "jdk"):
            continue
        if "jdk-" in d:
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
    if os.path.exists(APKSIGNER_BIN) and os.path.exists(D8_BIN) and os.path.exists(AAPT2_BIN):
        return
    zpath = os.path.join(TOOLS_DIR, "bt.zip")
    _download(URL_BUILDTOOLS, zpath)
    with zipfile.ZipFile(zpath) as z:
        z.extractall(TOOLS_DIR)
    picked = None
    for d in sorted(os.listdir(TOOLS_DIR)):
        full = os.path.join(TOOLS_DIR, d)
        if os.path.isdir(full) and d.startswith("android-") and "platform" not in d:
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
    for b in (APKSIGNER_BIN, ZIPALIGN_BIN, D8_BIN, AAPT2_BIN):
        if os.path.exists(b):
            os.chmod(b, os.stat(b).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def _extract_android_jar():
    """Platform-34 zip → android-34/android.jar → tools/android.jar"""
    if os.path.exists(ANDROID_JAR) and os.path.getsize(ANDROID_JAR) > 1_000_000:
        return
    zpath = os.path.join(TOOLS_DIR, "platform.zip")
    _download(URL_ANDROID_PLATFORM, zpath)

    extract_root = os.path.join(TOOLS_DIR, "_platform_tmp")
    if os.path.exists(extract_root):
        shutil.rmtree(extract_root)
    os.makedirs(extract_root, exist_ok=True)

    with zipfile.ZipFile(zpath) as z:
        z.extractall(extract_root)

    found = None
    for root, _, files in os.walk(extract_root):
        for fn in files:
            if fn == "android.jar":
                full = os.path.join(root, fn)
                if os.path.getsize(full) > 1_000_000:
                    found = full
                    break
        if found:
            break

    if not found:
        raise RuntimeError("android.jar not found in platform zip")

    if os.path.exists(ANDROID_JAR):
        os.remove(ANDROID_JAR)
    shutil.copy2(found, ANDROID_JAR)
    shutil.rmtree(extract_root, ignore_errors=True)
    if os.path.exists(zpath):
        os.remove(zpath)
    print(f"[✓] android.jar ({os.path.getsize(ANDROID_JAR)} bytes)", flush=True)


def _do_setup():
    _extract_jdk()
    _download(URL_APKTOOL, APKTOOL_JAR)
    _extract_build_tools()
    _extract_android_jar()
    with open(_READY_FLAG, "w") as f:
        f.write("ok")
    print("[✓] tools ready", flush=True)


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
            raise
        finally:
            _setup_done.set()


def wait_ready(timeout=900.0):
    if os.path.exists(_READY_FLAG):
        return True
    ok = _setup_done.wait(timeout)
    if _setup_error["exc"]:
        raise _setup_error["exc"]
    return ok and os.path.exists(_READY_FLAG)
