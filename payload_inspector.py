"""Payload APK se label + best icon nikalo."""
import os
import re
import subprocess
import zipfile
from config import AAPT2_BIN, JAVA_BIN


def _java_env() -> dict:
    env = os.environ.copy()
    jhome = os.path.dirname(os.path.dirname(JAVA_BIN))
    env["JAVA_HOME"] = jhome
    env["PATH"] = os.path.dirname(JAVA_BIN) + os.pathsep + env.get("PATH", "")
    return env


def get_label(apk_path: str) -> str:
    if not os.path.exists(AAPT2_BIN):
        return ""
    try:
        p = subprocess.run(
            [AAPT2_BIN, "dump", "badging", apk_path],
            capture_output=True, text=True, timeout=60, env=_java_env(),
        )
    except Exception:
        return ""
    if p.returncode != 0:
        return ""
    fallback = ""
    for line in p.stdout.splitlines():
        if line.startswith("application-label:"):
            return line.split(":", 1)[1].strip().strip("'\"").strip()
        if line.startswith("application-label-") and not fallback:
            fallback = line.split(":", 1)[1].strip().strip("'\"").strip()
    return fallback


_ICON_NAME_HINT = re.compile(r"ic_launcher|app_icon|^launcher", re.IGNORECASE)
_DENSITY_RANK = {
    "ldpi": 1, "mdpi": 2, "hdpi": 3, "xhdpi": 4, "xxhdpi": 5, "xxxhdpi": 6,
}


def _density_score(path: str) -> int:
    m = re.search(r"-(ldpi|mdpi|hdpi|xhdpi|xxhdpi|xxxhdpi)", path)
    if m:
        return _DENSITY_RANK.get(m.group(1), 0)
    return 0


def extract_best_icon(apk_path: str):
    """Best-matching launcher icon bytes + original ext. None if nothing."""
    candidates = []
    try:
        with zipfile.ZipFile(apk_path, "r") as z:
            for n in z.namelist():
                ln = n.lower()
                if not ln.startswith("res/"):
                    continue
                if not ln.endswith((".png", ".webp", ".jpg", ".jpeg")):
                    continue
                base = os.path.basename(ln)
                if not (_ICON_NAME_HINT.search(base) or "mipmap" in ln):
                    continue
                try:
                    data = z.read(n)
                except Exception:
                    continue
                if len(data) < 256:
                    continue
                score = _density_score(ln) * 1_000_000 + len(data)
                candidates.append((score, n, data))
    except Exception:
        return None

    if not candidates:
        return None

    candidates.sort(key=lambda t: t[0], reverse=True)
    _, name, data = candidates[0]
    ext = os.path.splitext(name)[1].lower()
    if ext not in (".png", ".webp", ".jpg", ".jpeg"):
        ext = ".png"
    return data, ext


def safe_xml_text(s: str) -> str:
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;")
             .replace("'", "&apos;"))
