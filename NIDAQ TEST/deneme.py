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
from nidaqmx.constants import LineGrouping, TerminalConfiguration
import time
import numpy as np

def read_sensors_precision():
    # Cihaz adını NI MAX üzerinden kontrol et (Genelde Dev1'dir)
    device_name = "Dev1"
    
    with nidaqmx.Task() as read_task, nidaqmx.Task() as write_task:
        # Analog Kanallar: RSE modunda 0-5V aralığında tanımlıyoruz
        # Bu, 16-bit çözünürlüğü 0-5V arasına sıkıştırarak hassasiyeti maksimize eder.
        read_task.ai_channels.add_ai_voltage_chan(
            f"{device_name}/ai0:3",
            terminal_config=TerminalConfiguration.RSE,
            min_val=0.0,
            max_val=5.0
        )
        
        # Dijital Çıkış: Toz Sensörü LED Tetikleme
        write_task.do_channels.add_do_chan(
            f"{device_name}/port0/line0", 
            line_grouping=LineGrouping.CHAN_FOR_ALL_LINES
        )

        print(f"{device_name} ile Yüksek Hassasiyetli Okuma Başlatıldı...")

        try:
            while True:
                # --- Hassas Okuma Döngüsü ---
                # Sinyal gürültüsünü engellemek için 100 adet örnek alıp ortalamasını buluyoruz
                samples = []
                for _ in range(100):
                    # Toz sensörü zamanlaması (Mikrosaniye hassasiyeti için kısa döngü)
                    write_task.write(True) 
                    time.sleep(0.00028)
                    sample = read_task.read()
                    write_task.write(False)
                    samples.append(sample)
                    time.sleep(0.001) # Örnekler arası kısa bekleyiş

                # Örneklerin ortalamasını al (Numpy ile hızlı hesaplama)
                avg_data = np.mean(samples, axis=0)

                # Voltaj Değerleri
                lm35_v = avg_data[0]
                mq7_v = avg_data[1]
                mq135_v = avg_data[2]
                dust_v = avg_data[3]

                # Birim Dönüşümleri
                # LM35: 10mV = 1°C -> Voltaj * 100
                sicaklik = lm35_v * 100 
                
                # Çıktı Ekranı
                print("-" * 50)
                print(f"Sıcaklık (Hassas): {sicaklik:.3f} °C") # 3 basamak hassasiyet
                print(f"MQ-7 Karbonmonoksit: {mq7_v:.4f} V")
                print(f"MQ-135 Hava Kalitesi: {mq135_v:.4f} V")
                print(f"Toz Sensörü Gerilimi: {dust_v:.4f} V")
                
                time.sleep(0.5) # Yarım saniyede bir güncelle

        except KeyboardInterrupt:
            print("\nKullanıcı tarafından durduruldu.")

if __name__ == "__main__":
    read_sensors_precision()