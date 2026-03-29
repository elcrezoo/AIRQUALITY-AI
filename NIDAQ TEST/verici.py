# -*- coding: utf-8 -*-

# ==============================================================================
# AeroSense AI — Akıllı Hava Kalitesi İzleme ve Analiz Sistemi
# -----------------------------------------------------------------------------
# Telif (Copyright) © 2026 Enes Bozkurt. Tüm hakları saklıdır.
# Karabük Üniversitesi (KBU) — Mekatronik Mühendisliği — 2026
# Web: https://enesbozkurt.com.tr
#
# Bu yazılım ve eşlik eden dokümantasyon, yazarın yazılı izni olmadan çoğaltılamaz,
# dağıtılamaz, kiralanamaz veya üçüncü kişilere devredilemez. Ticari kullanım yasaktır.
# Akademik ve proje sunumlarında kaynak gösterilmesi zorunludur.
# ==============================================================================

import nidaqmx
from nidaqmx.constants import TerminalConfiguration
import numpy as np
import socket
import json
import time

# Ayarlar
JETSON_IP = '10.25.110.103' # Buraya kendi Jetson IP'ni yaz
PORT = 5005

def pc_sender_all_sensors():
    with nidaqmx.Task() as task:
        # AI0'dan AI3'e kadar 4 kanalı RSE modunda açıyoruz
        task.ai_channels.add_ai_voltage_chan(
            "Dev1/ai0:3", 
            terminal_config=TerminalConfiguration.RSE,
            min_val=0.0, 
            max_val=5.0
        )

        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            client_socket.connect((JETSON_IP, PORT))
            print("Jetson'a bağlandı. Tüm sensör verileri gönderiliyor...")

            while True:
                # 100 örnek alıp ortalama alarak gürültüyü süzüyoruz
                raw_readings = task.read(number_of_samples_per_channel=100)
                # raw_readings 4 kanalın verisini içeren bir listedir
                avg_v = [np.mean(channel) for channel in raw_readings]

                # Sensör verilerini isimlendiriyoruz
                payload = {
                    "sicaklik": avg_v[0] * 100, # LM35 (10mV/C)
                    "mq7": avg_v[1],           # MQ7 Voltaj
                    "mq135": avg_v[2],         # MQ135 Voltaj
                    "toz": avg_v[3]            # Toz Sensörü Voltaj
                }

                # JSON formatında gönder
                client_socket.sendall(json.dumps(payload).encode('utf-8'))
                
                print(f"Gönderildi -> Sic: {payload['sicaklik']:.2f} | MQ7: {payload['mq7']:.3f} | MQ135: {payload['mq135']:.3f} | Toz: {payload['toz']:.3f}")
                time.sleep(1)

        except Exception as e:
            print(f"Hata: {e}")
        finally:
            client_socket.close()

if __name__ == "__main__":
    pc_sender_all_sensors()