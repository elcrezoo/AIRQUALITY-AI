<!--
  Telif © 2026 Enes Bozkurt · Karabük Üniversitesi (KBU) — Mekatronik Mühendisliği — 2026
  https://enesbozkurt.com.tr · Tüm hakları saklıdır. Bu belge izinsiz çoğaltılamaz.
-->

# AeroSense AI v2.0 — Adım Adım Kurulum Kılavuzu

**Proje sahibi:** Enes Bozkurt · **KBU Mekatronik Mühendisliği 2026** · **enesbozkurt.com.tr**

Bu belge, **NI DAQ 6002 + PC (verici)** ve **NVIDIA Jetson TX2 (alıcı, AI, masaüstü, API)** kurulumunu baştan sona anlatır.

---

## Ön koşullar

| Bileşen | Açıklama |
|--------|----------|
| PC | NI USB-6002 (veya uyumlu), NI-DAQmx, Python + `nidaqmx` |
| TX2 | Ubuntu 18.04 / JetPack 4.x önerilir, masaüstü oturumu (GUI için) |
| Ağ | PC ile TX2 aynı LAN’da; TX2 için sabit IP önerilir |

---

## Adım 1 — Projeyi Jetson’a kopyalayın

1. Bu depoyu TX2’ye kopyalayın (`git clone`, USB, `scp` vb.).
2. Klasör yolunda **boşluk olmaması** önerilir (örnek: `/home/jetson/AEROSENSE_AI`).
3. Kök dizinde şunlar bulunmalıdır: `main.py`, `aerosense_ai/`, `config/`, `requirements.txt`, `deploy/`, `scripts/`.

---

## Adım 2 — Jetson’da sistem paketlerini kurun

Terminalde:

```bash
sudo apt update
sudo apt install -y python3-pip python3-pyqt5 python3-pyqt5.qtsvg \
  espeak espeak-data libespeak1 libportaudio2 portaudio19-dev
```

**Sesli komut (isteğe bağlı):**

```bash
sudo apt install -y python3-pyaudio
pip3 install --user SpeechRecognition
```

---

## Adım 3 — Python bağımlılıklarını kurun

Proje kökünde:

```bash
cd /home/jetson/AEROSENSE_AI
pip3 install --user -r requirements.txt
```

Alternatif (betik):

```bash
bash scripts/install_jetson.sh
```

---

## Adım 4 — Jetson performans modu (önerilir)

AI ve arayüz için tam güç:

```bash
sudo nvpmodel -m 0
sudo jetson_clocks
```

Kalıcı yapmak için `systemd` birimindeki `ExecStartPre` satırlarını kullanabilir veya boot betiğinize ekleyebilirsiniz (kullanıcı yetkisi gerekebilir).

---

## Adım 5 — Ağ ve portları netleştirin

| Servis | Port | Açıklama |
|--------|------|----------|
| Sensör TCP (alıcı) | **5005** | PC `verici.py` → TX2 |
| REST API + web panel | **38471** | Tarayıcı ve mobil (varsayılan) |

TX2’de güvenlik duvarı kullanıyorsanız:

```bash
sudo ufw allow 5005/tcp
sudo ufw allow 38471/tcp
```

---

## Adım 6 — PC tarafında vericiyi yapılandırın

1. `NIDAQ TEST/verici.py` dosyasını açın.
2. **`JETSON_IP`** değerini TX2’nin IP adresi yapın (örnek: `192.168.1.50`).
3. **`PORT = 5005`** olduğundan emin olun.
4. DAQ cihaz adı `Dev1` değilse `"Dev1/ai0:3"` ifadesini kendi cihazınıza göre düzeltin.

---

## Adım 7 — İlk test: önce TX2, sonra PC

### 7.1 Jetson’da uygulamayı başlatın

Masaüstü oturumu açıkken:

```bash
cd /home/jetson/AEROSENSE_AI
python3 main.py
```

Beklenen: tam ekran veya büyük pencere, grafik alanı, AQI satırı.

### 7.2 PC’de vericiyi çalıştırın

```bash
python verici.py
```

**Sıra önemli:** Önce TX2 tarafı dinlemeye geçmeli; sonra PC bağlanır.

### 7.3 Doğrulama

- TX2’de grafikler güncelleniyor mu?
- `data/sensor_log.csv` ve `data/logs/YYYY-MM-DD.csv` dosyaları oluşuyor ve büyüyor mu?

---

## Adım 8 — Tarayıcı ve API testi

TX2 üzerinde veya aynı ağdaki telefon/PC tarayıcısından:

| Adres | Açıklama |
|-------|----------|
| `http://127.0.0.1:38471/` | Basit web panel |
| `http://<TX2_IP>:38471/api/status` | Sistem durumu (JSON) |
| `http://<TX2_IP>:38471/api/sensors/latest` | Son sensör + AI özeti |

`<TX2_IP>` yerine gerçek IP yazın.

---

## Adım 9 — Model eğitimi (isteğe bağlı, bir kez)

Yeterli satır birikmiş `data/sensor_log.csv` ile:

```bash
cd /home/jetson/AEROSENSE_AI
python3 scripts/train_model.py --csv data/sensor_log.csv --format aerosense
```

Oluşan dosyalar:

- `data/models/aerosense_model.joblib`
- `data/models/anomaly_iforest.joblib`

Model yoksa sistem kural tabanlı AQI ve basit anomali ile çalışır.

Eğitimden sonra (veya model dosyası değişince) çalışan sürece:

```bash
curl -X POST http://127.0.0.1:38471/api/model/reload
```

---

## Adım 10 — systemd ile otomatik başlatma

### 10.1 Servis dosyasını düzenleyin

`deploy/air-ai.service` içinde şunları **kendi sisteminize** göre değiştirin:

- `User=` / `Group=`
- `WorkingDirectory=`
- `ExecStart=` içindeki tam yol (`.../main.py`)
- `Environment=AEROSENSE_ROOT=...`

### 10.2 Kurulum komutları

```bash
sudo cp /home/jetson/AEROSENSE_AI/deploy/air-ai.service /etc/systemd/system/air-ai.service
sudo systemctl daemon-reload
sudo systemctl enable air-ai.service
sudo systemctl start air-ai.service
```

### 10.3 Durum ve loglar

```bash
sudo systemctl status air-ai.service
sudo journalctl -u air-ai.service -f
```

**Not:** Grafik arayüz için kullanıcının grafik oturumu (`DISPLAY=:0`, `XAUTHORITY`) gerekir. Oturum yokken GUI açılmaz; bu durumda ortam değişkeni `AEROSENSE_NO_GUI=1` ile yalnızca alıcı+API çalıştırılabilir veya masaüstü otomatik başlatma (`.desktop`) kullanılabilir.

---

## Adım 11 — Ortam değişkenleri (isteğe bağlı)

| Değişken | Örnek | Anlamı |
|----------|--------|--------|
| `AEROSENSE_ROOT` | `/home/jetson/AEROSENSE_AI` | Veri/model kökü |
| `AEROSENSE_PORT` | `5005` | Sensör TCP portu |
| `AEROSENSE_API_PORT` | `38471` | API portu (gerekirse 5000, 8765 vb. verin) |
| `AEROSENSE_VOICE` | `0` | Sesli okuma kapalı |
| `AEROSENSE_FULLSCREEN` | `0` | Tam ekran kapalı |
| `AEROSENSE_NO_GUI` | `1` | PyQt penceresi yok |
| `AEROSENSE_ADMIN_PASSWORD` | `gizli` | `/api/system/restart` için şifre |

`systemd` içinde örnek:

```ini
Environment=AEROSENSE_API_PORT=38471
Environment=AEROSENSE_VOICE=1
```

---

## Adım 12 — NI DAQ kanal algılama (sadece PC, isteğe bağlı)

DAQ’ın takılı olduğu bilgisayarda NI-DAQmx varken:

```bash
cd /path/to/AEROSENSE_AI
PYTHONPATH=. python3 hardware/sensor_detector.py
```

Çıktı: `config/active_sensors.json` güncellenir. Jetson’da DAQ olmadığı için bu adım **zorunlu değildir**; varsayılan `config/active_sensors.json` yeterlidir.

---

## Adım 13 — `NIDAQ TEST/alıcı.py` hakkında

Bu dosya, proje kökünü yola ekleyerek **tam AeroSense** uygulamasını başlatır (`main.py` ile aynı akış). Jetson’da günlük kullanım için doğrudan şunu tercih edin:

```bash
python3 main.py
```

---

## Sorun giderme (kısa)

| Sorun | Olası neden | Ne yapın |
|-------|-------------|----------|
| PC bağlanamıyor | TX2 çalışmıyor veya IP/port yanlış | Önce TX2’de `main.py`; `JETSON_IP` ve 5005 |
| GUI yok | DISPLAY yok veya PyQt5 eksik | Masaüstü oturumu; `apt install python3-pyqt5` |
| API yanıt vermiyor | Port meşgul veya firewall | `38471` açık mı; `AEROSENSE_API_PORT` |
| Ses yok | TTS kapalı veya sürücü | `AEROSENSE_VOICE=1`; espeak kurulu mu |
| Model hatası | Sütun adları farklı | CSV’de `sicaklik`, `mq7`, `mq135`, `toz` uyumu |

---

## Özet komut listesi (Jetson)

```bash
sudo apt update && sudo apt install -y python3-pip python3-pyqt5 python3-pyqt5.qtsvg espeak espeak-data libespeak1 libportaudio2 portaudio19-dev
cd /home/jetson/AEROSENSE_AI
pip3 install --user -r requirements.txt
sudo nvpmodel -m 0 && sudo jetson_clocks
python3 main.py
```

Ardından PC’de `verici.py` çalıştırın.

---

**AeroSense AI v2.0** — NVIDIA Jetson TX2 · NI DAQ 6002 · Python AI Engine

---

### Telif ve atıf (zorunlu bildirim)

**Copyright © 2026 Enes Bozkurt.** Tüm hakları saklıdır.  
**Karabük Üniversitesi (KBU) — Mekatronik Mühendisliği — 2026**  
**Web:** [enesbozkurt.com.tr](https://enesbozkurt.com.tr)

Bu kurulum kılavuzu ve bağlı olduğu **AeroSense AI** yazılımı; yazarın yazılı izni olmadan çoğaltılamaz, dağıtılamaz veya ticari amaçla kullanılamaz. Akademik kullanımda kaynak gösterilmesi zorunludur.

---

*Filigran / telif metinleri ayrıca `README.md`, `TELIF.md`, kaynak dosya başlıkları ve `aerosense_ai/project_meta.py` içinde yer alır.*
