import os
import subprocess
import threading
import time
from config import JAVA_BIN


def java_env() -> dict:
    env = os.environ.copy()
    jhome = os.path.dirname(os.path.dirname(JAVA_BIN))
    env["JAVA_HOME"] = jhome
    env["PATH"] = os.path.dirname(JAVA_BIN) + os.pathsep + env.get("PATH", "")
    return env


def run_stream(cmd, timeout: int = 1800, label: str = "cmd", env: dict = None):
    if env is None:
        env = java_env()
    print(f"[>] {label}: {' '.join(cmd)}", flush=True)
    t0 = time.time()
    try:
        p = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            env=env,
        )
    except Exception as e:
        raise RuntimeError(f"[!] spawn failed {label}: {e}")

    lines = []

    def _reader():
        try:
            for raw in p.stdout:
                line = raw.rstrip()
                if line:
                    lines.append(line)
                    print(f"    | {line}", flush=True)
        except Exception:
            pass

    th = threading.Thread(target=_reader, daemon=True)
    th.start()

    try:
        p.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        p.kill()
        try:
            p.wait(timeout=5)
        except Exception:
            pass
        raise RuntimeError(f"[!] timeout {timeout}s: {label}")

    th.join(timeout=3)

    if p.returncode != 0:
        tail = "\n".join(lines[-40:])
        raise RuntimeError(f"[!] rc={p.returncode} {label}\n{tail}")

    print(f"[✓] {label} done {time.time() - t0:.1f}s", flush=True)
