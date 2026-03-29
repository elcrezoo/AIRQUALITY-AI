<!--
  AeroSense AI — Akıllı Hava Kalitesi İzleme ve Analiz Sistemi
  Telif © 2026 Enes Bozkurt. Tüm hakları saklıdır.
  Karabük Üniversitesi (KBU) — Mekatronik Mühendisliği — 2026
  https://enesbozkurt.com.tr
-->

# AeroSense AI v2.0

**Akıllı hava kalitesi izleme ve analiz sistemi** — NVIDIA Jetson TX2, NI DAQ 6002, Python tabanlı AI motoru, PyQt5 masaüstü ve Flask REST API.

---

## Proje sahibi ve telif (filigran)

| | |
|---|---|
| **Geliştirici** | **Enes Bozkurt** |
| **Kurum / Bölüm** | Karabük Üniversitesi (KBU) — Mekatronik Mühendisliği — **2026** |
| **Web** | [enesbozkurt.com.tr](https://enesbozkurt.com.tr) |

**Telif hakkı:** Copyright © 2026 **Enes Bozkurt**. Tüm hakları saklıdır.

Bu yazılım, kaynak kodları ve eşlik eden dokümantasyon (README, KURULUM, teknik belgeler vb.), yazarın **yazılı izni olmadan** kısmen veya tamamen çoğaltılamaz, dağıtılamaz, kiralanamaz, satılamaz veya üçüncü kişilere devredilemez. **Ticari kullanım yasaktır.** Akademik çalışma, tez, rapor veya proje sunumlarında kullanımda **kaynak gösterilmesi zorunludur** (yazar adı, kurum, yıl ve web sitesi).

Bu depo ve ürünleştirilmiş sürümler üzerindeki morali ve mali haklar Enes Bozkurt’a aittir.

---

## Özellikler (özet)

- NI DAQ üzerinden toplanan sensör verisinin TX2’ye iletilmesi (TCP), sürekli CSV loglama
- Kural tabanlı + isteğe bağlı makine öğrenmesi (AQI sınıfları, anomali)
- PyQt5 tam ekran masaüstü arayüzü, Flask API ve basit web paneli
- Sesli geri bildirim ve isteğe bağlı sesli komut
- `systemd` ile otomatik başlatma ve yeniden başlatma

---

## Windows / PC’de arayüz önizlemesi (TX2 yokken)

Jetson yanınızda değilken masaüstü arayüzü ve grafikleri görmek için mevcut bilgisayarınızda çalıştırabilirsiniz.

1. Python 3.7+ önerilir. Proje klasöründe:
   ```bash
   pip install -r requirements.txt
   ```
2. **Sahte sensör modu** (TX2 ve NI DAQ vericisi gerekmez; grafikler canlı hareket eder):
   - **PowerShell:**
     ```powershell
     cd "C:\Users\...\AIRQUALITY AI"
     $env:AEROSENSE_MOCK="1"
     $env:AEROSENSE_VOICE="1"
     python main.py
     ```
   - **cmd:**
     ```cmd
     set AEROSENSE_MOCK=1
     set AEROSENSE_VOICE=1
     python main.py
     ```
3. Tarayıcıdan panel: `http://127.0.0.1:38471/` (API varsayılan portu **38471**).

**Ses:** `AEROSENSE_VOICE=1` → konuşma (TTS). `AEROSENSE_VOICE_COMMANDS=1` (varsayılan) → mikrofonla “durum / hava kalitesi” vb. İkisi bağımsız: TTS’i kapatıp sadece komut için `AEROSENSE_VOICE=0` bırakabilirsiniz. Otomatik AI ses uyarısı: `AEROSENSE_VOICE_ALERTS=1` (varsayılan). Tam ekran: `AEROSENSE_FULLSCREEN=0`.

Mock kapalıyken PC’de de çalışır; ancak veri gelmezse grafik boş kalır (sadece TCP `5005`’e bağlanan verici veri gönderirse dolar).

---

## Kurulum

Adım adım talimatlar için projedeki **`KURULUM.md`** dosyasına bakın.

Hızlı başlangıç (Jetson):

```bash
pip3 install --user -r requirements.txt
python3 main.py
```

---

## Teknik özet

- **Python:** 3.6+ (Ubuntu 18.04 / Jetson TX2 uyumu)
- **Giriş noktası:** `main.py`
- **Paket:** `aerosense_ai/`
- **API varsayılan port:** 38471 · **Sensör TCP:** 5005

Telif ve proje kimliği programatik olarak `aerosense_ai.project_meta` modülünde ve API yanıtlarında (`/api/status`, `/api/health`) yer alır; HTTP yanıtlarında `X-AeroSense-Notice` başlığı kullanılır.

---

## İletişim

**Enes Bozkurt** — [enesbozkurt.com.tr](https://enesbozkurt.com.tr)  
KBU Mekatronik Mühendisliği · 2026

---

*Bu README, AeroSense AI projesinin ayrılmaz parçasıdır ve telif bildirimi taşımak zorundadır.*
