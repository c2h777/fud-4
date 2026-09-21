import os


def randomize_manifest(decompiled_dir: str):
    """
    Package rename NAHI karte. Tumhare smali me Class.forName() refs hain
    jo runtime getPackageName() use karte hain. Rename karne se
    VpnKillService/RcvJbrzn/MainActivity ka lookup toot jaata hai.
    """
    path = os.path.join(decompiled_dir, "AndroidManifest.xml")
    if os.path.exists(path):
        size = os.path.getsize(path)
        print(f"[i] manifest untouched ({size} bytes)", flush=True)
    else:
        print("[!] manifest missing", flush=True)
