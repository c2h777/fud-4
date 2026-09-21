import os
import shutil
from config import JAVA_BIN, APKTOOL_JAR
from _proc import run_stream


def decompile(apk_path: str, output_dir: str):
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir, exist_ok=True)
    run_stream(
        [JAVA_BIN, "-jar", APKTOOL_JAR, "d", "-f",
         "-o", output_dir, apk_path],
        timeout=600, label="apktool-d",
    )
    print(f"[✓] decompiled → {output_dir}", flush=True)


def recompile(decompiled_dir: str, output_apk: str):
    if os.path.exists(output_apk):
        os.remove(output_apk)
    run_stream(
        [JAVA_BIN, "-jar", APKTOOL_JAR, "b",
         decompiled_dir, "-o", output_apk],
        timeout=600, label="apktool-b",
    )
    print(f"[✓] recompiled → {output_apk}", flush=True)
