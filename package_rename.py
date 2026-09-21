"""Random package name rename — manifest + smali + apktool.yml."""
import os
import random
import re
import shutil
import string


def _rand_pkg():
    parts = []
    for _ in range(3):
        n = random.randint(4, 8)
        s = random.choice(string.ascii_lowercase) + "".join(
            random.choices(string.ascii_lowercase + string.digits, k=n - 1)
        )
        parts.append(s)
    return ".".join(parts)


def _smali_roots(decompiled_dir):
    roots = []
    for d in sorted(os.listdir(decompiled_dir)):
        full = os.path.join(decompiled_dir, d)
        if os.path.isdir(full) and (d == "smali" or d.startswith("smali_classes")):
            roots.append(full)
    return roots


def rename_package(decompiled_dir: str) -> str:
    """Randomize package. Returns new package name."""
    manifest = os.path.join(decompiled_dir, "AndroidManifest.xml")
    if not os.path.exists(manifest):
        raise RuntimeError("manifest missing")

    with open(manifest, "r", encoding="utf-8") as f:
        mxml = f.read()

    m = re.search(r'package="([^"]+)"', mxml)
    if not m:
        raise RuntimeError("package attr not found in manifest")
    old_pkg = m.group(1)
    new_pkg = _rand_pkg()

    old_path = old_pkg.replace(".", "/")
    new_path = new_pkg.replace(".", "/")

    # 1) manifest string replace
    mxml = mxml.replace(f'package="{old_pkg}"', f'package="{new_pkg}"')
    mxml = mxml.replace(f'android:name="{old_pkg}.', f'android:name="{new_pkg}.')
    mxml = mxml.replace(f'android:targetPackage="{old_pkg}"',
                        f'android:targetPackage="{new_pkg}"')
    with open(manifest, "w", encoding="utf-8") as f:
        f.write(mxml)

    # 2) smali folders
    for root in _smali_roots(decompiled_dir):
        src_dir = os.path.join(root, old_path)
        dst_dir = os.path.join(root, new_path)
        if os.path.isdir(src_dir):
            os.makedirs(os.path.dirname(dst_dir), exist_ok=True)
            if os.path.exists(dst_dir):
                shutil.rmtree(dst_dir)
            shutil.move(src_dir, dst_dir)

        # replace refs in every smali file
        old_ref = f"L{old_path}/"
        new_ref = f"L{new_path}/"
        for dirpath, _, files in os.walk(root):
            for fn in files:
                if not fn.endswith(".smali"):
                    continue
                fp = os.path.join(dirpath, fn)
                try:
                    with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                        txt = f.read()
                except Exception:
                    continue
                if old_ref in txt:
                    txt = txt.replace(old_ref, new_ref)
                    with open(fp, "w", encoding="utf-8") as f:
                        f.write(txt)

    # 3) apktool.yml
    yml = os.path.join(decompiled_dir, "apktool.yml")
    if os.path.exists(yml):
        with open(yml, "r", encoding="utf-8", errors="ignore") as f:
            txt = f.read()
        txt = txt.replace(old_pkg, new_pkg)
        with open(yml, "w", encoding="utf-8") as f:
            f.write(txt)

    # 4) resources.arsc can't be edited easily — but res/values/strings.xml
    # and any res/.../public.xml may hold old pkg as string. Best-effort.
    for dirpath, _, files in os.walk(os.path.join(decompiled_dir, "res")):
        for fn in files:
            if not fn.endswith(".xml"):
                continue
            fp = os.path.join(dirpath, fn)
            try:
                with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                    txt = f.read()
            except Exception:
                continue
            if old_pkg in txt:
                txt = txt.replace(old_pkg, new_pkg)
                with open(fp, "w", encoding="utf-8") as f:
                    f.write(txt)

    print(f"[✓] package renamed: {old_pkg} → {new_pkg}", flush=True)
    return new_pkg
