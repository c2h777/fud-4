import os
import random
import string
import xml.etree.ElementTree as ET

ANDROID_NS = "http://schemas.android.com/apk/res/android"
ET.register_namespace("android", ANDROID_NS)


def _rand_pkg():
    return ".".join(
        "".join(random.choices(string.ascii_lowercase, k=random.randint(4, 7)))
        for _ in range(3)
    )


def _rand_meta_name():
    return "cfg_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=10))


def randomize_manifest(decompiled_dir: str):
    """
    apktool ka output = plain XML. Rename package, inject junk <meta-data>,
    aur version bump. Ye scanner ke manifest fingerprint ko todta hai.
    """
    path = os.path.join(decompiled_dir, "AndroidManifest.xml")
    tree = ET.parse(path)
    root = tree.getroot()

    old_pkg = root.get("package") or ""
    new_pkg = _rand_pkg()
    root.set("package", new_pkg)

    app = root.find("application")
    if app is not None:
        # junk meta-data
        for _ in range(random.randint(2, 4)):
            md = ET.SubElement(app, "meta-data")
            md.set(f"{{{ANDROID_NS}}}name", _rand_meta_name())
            md.set(f"{{{ANDROID_NS}}}value",
                   "".join(random.choices(string.ascii_letters + string.digits, k=24)))

    tree.write(path, encoding="utf-8", xml_declaration=True)

    # yml ke andar bhi package update karo (apktool b isse padhta hai)
    yml = os.path.join(decompiled_dir, "apktool.yml")
    if os.path.exists(yml) and old_pkg:
        with open(yml, "r", encoding="utf-8") as f:
            data = f.read()
        data = data.replace(old_pkg, new_pkg)
        with open(yml, "w", encoding="utf-8") as f:
            f.write(data)

    print(f"[✓] manifest randomized: {old_pkg} → {new_pkg}")
    return new_pkg
