import os
import shutil
import subprocess
from config import JAVA_BIN, APKTOOL_JAR


def _env():
    env = os.environ.copy()
    env["JAVA_HOME"] = os.path.dirname(os.path.dirname(JAVA_BIN))
    env["PATH"] = os.path.dirname(JAVA_BIN) + os.pathsep + env.get("PATH", "")
    return env


def _run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True, env=_env())
    if p.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)}\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}")
    return p.stdout


def decompile(apk_path: str, output_dir: str):
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    _run([JAVA_BIN, "-jar", APKTOOL_JAR, "d", "-f", "-o", output_dir, apk_path])
    print(f"[✓] apktool decompiled → {output_dir}")


def recompile(decompiled_dir: str, output_apk: str):
    if os.path.exists(output_apk):
        os.remove(output_apk)
    _run([JAVA_BIN, "-jar", APKTOOL_JAR, "b", decompiled_dir, "-o", output_apk])
    print(f"[✓] apktool recompiled → {output_apk}")
