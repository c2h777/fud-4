import os
import shutil
import subprocess
from config import (
    JAVA_BIN, APKSIGNER_BIN, ZIPALIGN_BIN,
    KEYSTORE_PATH, KEYSTORE_PASS, KEY_ALIAS,
)


def _run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"cmd failed: {' '.join(cmd)}\n{p.stdout}\n{p.stderr}")
    return p.stdout


def sign_apk(unsigned_apk: str, output_apk: str):
    tmp_aligned = unsigned_apk + ".aligned"

    # 1) zipalign — MUST be before signing (v2/v3 sign covers alignment)
    _run([ZIPALIGN_BIN, "-f", "-p", "4", unsigned_apk, tmp_aligned])

    # 2) apksigner — v1 + v2 + v3 all enabled
    _run([
        APKSIGNER_BIN, "sign",
        "--ks", KEYSTORE_PATH,
        "--ks-pass", f"pass:{KEYSTORE_PASS}",
        "--ks-key-alias", KEY_ALIAS,
        "--key-pass", f"pass:{KEYSTORE_PASS}",
        "--v1-signing-enabled", "true",
        "--v2-signing-enabled", "true",
        "--v3-signing-enabled", "true",
        "--out", output_apk,
        tmp_aligned,
    ])
    os.remove(tmp_aligned)
    print(f"[✓] signed (v1+v2+v3) → {output_apk}")
