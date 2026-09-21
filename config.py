import os

BOT_TOKEN     = "8902950524:AAFxUFbICKx4sm5JM-WGudYOSfjR3w59_Dk"
_HOME         = os.path.expanduser("~")
TOOLS_DIR     = os.path.join(_HOME, "tools")
KEYSTORE_PATH = os.path.join(TOOLS_DIR, "release.p12")
KEYSTORE_PASS = "fudbot123"
KEY_ALIAS     = "fudkey"
WORK_DIR      = os.path.join(_HOME, "fud_workspace")

# ---- tool paths (setup.py inhe populate karega) ----
JAVA_BIN       = os.path.join(TOOLS_DIR, "jre", "bin", "java")
APKTOOL_JAR    = os.path.join(TOOLS_DIR, "apktool.jar")
APKSIGNER_BIN  = os.path.join(TOOLS_DIR, "build-tools", "apksigner")
ZIPALIGN_BIN   = os.path.join(TOOLS_DIR, "build-tools", "zipalign")
D8_BIN         = os.path.join(TOOLS_DIR, "build-tools", "d8")

# ---- loader build artifacts (cached) ----
LOADER_SRC_DIR = os.path.join(TOOLS_DIR, "loader_src")
LOADER_DEX     = os.path.join(TOOLS_DIR, "loader.dex")
LOADER_SO_DIR  = os.path.join(TOOLS_DIR, "loader_libs")   # abi subdirs
