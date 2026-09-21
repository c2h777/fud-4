import os
import random
import string


def rand_str(k=8):
    return ''.join(random.choices(string.ascii_lowercase, k=k))


def inject_junk(decompiled_dir: str, count: int = 8):
    """
    res/raw me reference-less files daalna pointless tha.
    Ab: assets/ me random binary blobs — entropy badhata hai,
    APK valid rehti hai, koi reference nahi chahiye.
    """
    assets = os.path.join(decompiled_dir, "assets")
    os.makedirs(assets, exist_ok=True)

    for _ in range(count):
        fname = rand_str(12) + ".dat"
        size = random.randint(1024, 16 * 1024)
        blob = bytes(random.getrandbits(8) for _ in range(size))
        with open(os.path.join(assets, fname), "wb") as f:
            f.write(blob)

    print(f"[✓] {count} junk blobs → assets/")
