#!/bin/bash
# © 2026 Enes Bozkurt | KBU Mekatronik Mühendisliği 2026 | enesbozkurt.com.tr
# Tüm hakları saklıdır.
# Jetson TX2 / Ubuntu 18.04+ — bagimlilik ve systemd kurulum yardimcisi
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
echo "AeroSense kok: $ROOT"

sudo apt-get update
sudo apt-get install -y python3-pip python3-pyqt5 python3-pyqt5.qtsvg espeak espeak-data libespeak1 \
  libportaudio2 portaudio19-dev || true

pip3 install --user -r "$ROOT/requirements.txt"

echo ""
echo "Performans (her acilista veya bir kez):"
echo "  sudo nvpmodel -m 0 && sudo jetson_clocks"
echo ""
echo "systemd: deploy/air-ai.service icindeki User, WorkingDirectory ve ExecStart yollarini duzenleyip:"
echo "  sudo cp $ROOT/deploy/air-ai.service /etc/systemd/system/air-ai.service"
echo "  sudo systemctl daemon-reload && sudo systemctl enable --now air-ai.service"
echo ""
echo "Alternatif: LightDM oturumunda ~/.config/autostart/aerosense.desktop ile run_aerosense.py calistirin."
echo "CSV: $ROOT/data/sensor_log.csv | Gunluk: $ROOT/data/logs/"
echo "API: http://<ip>:38471/api/sensors/latest — panel: http://<ip>:38471/"
echo "Giris: python3 $ROOT/main.py"
