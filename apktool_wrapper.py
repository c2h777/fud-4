import os
import shutil
import zipfile

# Yeh files STORE mode mein rakhni hain — compress nahi karni
_STORE_EXTS  = {".dex", ".arsc", ".png", ".jpg", ".jpeg",
                ".gif", ".webp", ".mp4", ".mp3", ".ogg", ".wav", ".so"}
_STORE_NAMES = {"AndroidManifest.xml", "resources.arsc"}


def _ctype(arcname: str) -> int:
    base = os.path.basename(arcname)
    ext  = os.path.splitext(base)[1].lower()
    if base in _STORE_NAMES or ext in _STORE_EXTS:
        return zipfile.ZIP_STORED
    return zipfile.ZIP_DEFLATED


def decompile(apk_path: str, output_dir: str):
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir, exist_ok=True)
    with zipfile.ZipFile(apk_path, "r") as zf:
        zf.extractall(output_dir)
    # Purani META-INF hata do — signer fresh sign karega
    meta = os.path.join(output_dir, "META-INF")
    if os.path.exists(meta):
        shutil.rmtree(meta)
    print(f"[✓] Decompiled → {output_dir}")


def recompile(decompiled_dir: str, output_apk: str):
    if os.path.exists(output_apk):
        os.remove(output_apk)
    with zipfile.ZipFile(output_apk, "w") as zf:
        # classes.dex PEHLE — Android requirement
        dex_files = []
        other_files = []
        for root, dirs, files in os.walk(decompiled_dir):
            dirs[:] = [d for d in dirs if d != "META-INF"]
            for fname in files:
                fpath   = os.path.join(root, fname)
                arcname = os.path.relpath(fpath, decompiled_dir).replace(os.sep, "/")
                if arcname.endswith(".dex"):
                    dex_files.append((fpath, arcname))
                else:
                    other_files.append((fpath, arcname))
        for fpath, arcname in dex_files:
            zf.write(fpath, arcname, compress_type=zipfile.ZIP_STORED)
        for fpath, arcname in other_files:
            zf.write(fpath, arcname, compress_type=_ctype(arcname))
    print(f"[✓] Recompiled → {output_apk}")
