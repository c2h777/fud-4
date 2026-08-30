import os
import re
import random
import string


def random_package_name():
    parts = [''.join(random.choices(string.ascii_lowercase,
                                    k=random.randint(4, 7))) for _ in range(3)]
    return '.'.join(parts)


def randomize_manifest(decompiled_dir: str):
    """
    Binary AXML modify karna risky hai — APK corrupt ho jaata hai.
    Isliye manifest mein kuch touch NAHI karte.
    FUD obfuscation DEX mutation aur junk injection se hoti hai.
    """
    # Safe: sirf log karo
    manifest_path = os.path.join(decompiled_dir, "AndroidManifest.xml")
    if os.path.exists(manifest_path):
        size = os.path.getsize(manifest_path)
        print(f"[✓] Manifest present ({size} bytes) — binary AXML, skip modification.")
    else:
        print("[!] Manifest nahi mila.")
