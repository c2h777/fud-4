#!/usr/bin/env bash
set -e

echo "[*] Installing Python deps..."
pip install -r requirements.txt

echo "[*] Checking Java..."
java -version || (
    echo "[*] Java nahi hai — install karo"
    apt-get update -qq && apt-get install -y -qq default-jdk
)

echo "[*] Build done."
