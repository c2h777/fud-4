import os
import random
import string


def rand_str(k=8):
    return ''.join(random.choices(string.ascii_lowercase, k=k))


def inject_junk(decompiled_dir: str, count: int = 8):
    """
    res/raw/ mein fake XML files inject karo.
    APK structure valid rehti hai — sirf extra files add hoti hain.
    """
    res_dir = os.path.join(decompiled_dir, "res", "raw")
    os.makedirs(res_dir, exist_ok=True)

    injected = 0
    for _ in range(count):
        fname   = rand_str(10) + ".xml"
        content = (
            '<?xml version="1.0" encoding="utf-8"?>\n'
            f'<resources>\n'
            f'  <string name="{rand_str(6)}">'
            f'{"".join(random.choices(string.ascii_letters + string.digits, k=random.randint(24, 64)))}'
            f'</string>\n'
            f'</resources>\n'
        )
        with open(os.path.join(res_dir, fname), "w", encoding="utf-8") as f:
            f.write(content)
        injected += 1

    print(f"[✓] {injected} junk files injected → res/raw/")
