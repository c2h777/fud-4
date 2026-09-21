import os
import shutil
import subprocess
from config import JAVA_BIN, APKTOOL_JAR


def _run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"cmd failed: {' '.join(cmd)}\n{p.stdout}\n{p.stderr}")
    return p.stdout


def decompile(apk_path: str, output_dir: str):
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    _run([JAVA_BIN, "-jar", APKTOOL_JAR, "d", "-f", "-o", output_dir, apk_path])
    # purge stale signatures
    meta = os.path.join(output_dir, "original", "META-INF")
    if os.path.exists(meta):
        shutil.rmtree(meta)
    print(f"[✓] apktool decompiled → {output_dir}")


def recompile(decompiled_dir: str, output_apk: str):
    if os.path.exists(output_apk):
        os.remove(output_apk)
    _run([JAVA_BIN, "-jar", APKTOOL_JAR, "b", decompiled_dir, "-o", output_apk])
    print(f"[✓] apktool recompiled → {output_apk}")
