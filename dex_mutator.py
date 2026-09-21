"""
Original string-bit-flip REMOVED — runtime crash karta tha.
Ab: no-op by default. Real obfuscation ke liye R8 use karo (build-time),
ya ProGuard rules. Apktool ke through obfuscation nahi karte.
"""
import os


def mutate_smali(decompiled_dir: str):
    dex_count = sum(
        1 for _, _, files in os.walk(decompiled_dir)
        for f in files if f.endswith(".dex")
    )
    print(f"[i] dex_mutator: {dex_count} dex — skipped (R8 handles obfuscation).")
