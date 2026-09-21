"""Auto-download: JRE, ecj, apktool, build-tools, android.jar. Keystore pipeline banata hai."""
import os
import shutil
import stat
import tarfile
import threading
import urllib.request
import zipfile
from config import (
    TOOLS_DIR,
    JAVA_BIN, ECJ_JAR, APKTOOL_JAR, BT_DIR,
    APKSIGNER_BIN, ZIPALIGN_BIN, D8_BIN, ANDROID_JAR,
    URL_JRE, URL_ECJ, URL_APKTOOL, URL_BUILDTOOLS,
)

PLATFORM_JAR_URLS = [
    "https://raw.githubusercontent.com/Sable/android-platforms/master/android-30/android.jar",
    "https://github.com/Sable/android-platforms/raw/master/android-30/android.jar",
]

_READY_FLAG = os.path.join(TOOLS_DIR, ".ready_v4")
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


def _do_setup():
    _extract_jre()
    _download(URL_ECJ, ECJ_JAR)
    _download(URL_APKTOOL, APKTOOL_JAR)
    _extract_build_tools()
    _extract_platform()
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
