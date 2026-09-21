import os
from config import (
    APKSIGNER_BIN, ZIPALIGN_BIN,
    KEYSTORE_PATH, KEYSTORE_PASS, KEY_ALIAS,
)
from _proc import run_stream


def sign_apk(unsigned_apk: str, output_apk: str):
    aligned = unsigned_apk + ".aligned"

    run_stream(
        [ZIPALIGN_BIN, "-f", "-p", "4", unsigned_apk, aligned],
        timeout=300, label="zipalign",
    )

    run_stream(
        [
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
        ],
        timeout=600, label="apksigner",
    )

    if os.path.exists(aligned):
        os.remove(aligned)
    print(f"[✓] signed → {output_apk}", flush=True)
