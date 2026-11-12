#!/bin/bash
echo "[*] Updating packages..."
pkg update -y && pkg upgrade -y
pkg install python -y
echo "[*] Installing requirements..."
pip install -r requirements.txt
echo "[+] Installation Complete! Run 'python app.py' to start."
