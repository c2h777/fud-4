import os
import subprocess
from config import (
    JAVA_BIN, APKSIGNER_BIN, ZIPALIGN_BIN,
    KEYSTORE_PATH, KEYSTORE_PASS, KEY_ALIAS,
)


def _env():
    env = os.environ.copy()
    env["JAVA_HOME"] = os.path.dirname(os.path.dirname(JAVA_BIN))
    env["PATH"] = os.path.dirname(JAVA_BIN) + os.pathsep + env.get("PATH", "")
    return env


def _run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True, env=_env())
    if p.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)}\n{p.stdout}\n{p.stderr}")


def sign_apk(unsigned_apk: str, output_apk: str):
    aligned = unsigned_apk + ".aligned"
    _run([ZIPALIGN_BIN, "-f", "-p", "4", unsigned_apk, aligned])
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
        aligned,
    ])
    if os.path.exists(aligned):
        os.remove(aligned)
    print(f"[✓] signed (v1+v2+v3) → {output_apk}")
