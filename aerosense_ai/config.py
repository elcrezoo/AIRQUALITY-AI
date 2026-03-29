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

"""Yollar ve varsayılan ayarlar. TX2 üzerinde /opt/aerosense veya home altına kurun."""
import os

# Proje kökü: bu dosyanın bulunduğu dizinin üstü
_PKG = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get("AEROSENSE_ROOT", os.path.dirname(_PKG))

DATA_DIR = os.path.join(ROOT, "data")
LOGS_DIR = os.environ.get("AEROSENSE_LOGS", os.path.join(DATA_DIR, "logs"))
MODEL_DIR = os.path.join(DATA_DIR, "models")
CONFIG_DIR = os.path.join(ROOT, "config")
CSV_PATH = os.environ.get("AEROSENSE_CSV", os.path.join(DATA_DIR, "sensor_log.csv"))

for _d in (DATA_DIR, MODEL_DIR, LOGS_DIR, CONFIG_DIR):
    if not os.path.isdir(_d):
        try:
            os.makedirs(_d)
        except OSError:
            pass

MODEL_PATH = os.path.join(MODEL_DIR, "aerosense_model.joblib")
SCALER_PATH = os.path.join(MODEL_DIR, "aerosense_scaler.joblib")
ANOMALY_MODEL_PATH = os.path.join(MODEL_DIR, "anomaly_iforest.joblib")
ACTIVE_SENSORS_JSON = os.path.join(CONFIG_DIR, "active_sensors.json")
MODEL_CONFIG_JSON = os.path.join(CONFIG_DIR, "model_config.json")
# GUI ve bildirimler — yerel JSON (Telegram vb.); repoya commit etmeyin
USER_SETTINGS_JSON = os.path.join(CONFIG_DIR, "user_settings.json")

# Marka görselleri — proje kökünde logo/ veya LOGO/ (Linux'ta büyük-küçük harf ayrımı var)
def _logo_roots():
    roots = []
    for sub in ("logo", "LOGO", "Logo"):
        p = os.path.join(ROOT, sub)
        if os.path.isdir(p):
            roots.append(p)
    if not roots:
        roots = [os.path.join(ROOT, "logo")]
    return roots


LOGO_SEARCH_ROOTS = _logo_roots()
LOGO_DIR = LOGO_SEARCH_ROOTS[0]


def _first_existing_file(candidates):
    for p in candidates:
        if p and os.path.isfile(p):
            return os.path.normpath(p)
    return None


def _first_under_logo_dirs(filenames):
    """Önce logo/, sonra LOGO/ ... içinde dosya ara."""
    for name in filenames:
        for base in LOGO_SEARCH_ROOTS:
            full = os.path.join(base, name)
            if os.path.isfile(full):
                return os.path.normpath(full)
    return None


_env_icon = os.environ.get("AEROSENSE_ICON", "").strip()
_env_splash = os.environ.get("AEROSENSE_SPLASH", "").strip()

# Görev çubuğu / pencere: Windows'ta .ico tercih edilir
WINDOW_ICON_PATH = _env_icon or _first_under_logo_dirs(
    ["icon.ico", "app.ico", "logo.ico", "icon.png", "logo.png"]
)

# Açılış ekranı (splash); yoksa atlanır
SPLASH_IMAGE_PATH = _env_splash or _first_under_logo_dirs(
    ["splash.png", "splash.jpg", "opening.png", "logo.png"]
)

# Alıcı (TX2) — verici.py ile aynı port
LISTEN_HOST = os.environ.get("AEROSENSE_LISTEN", "0.0.0.0")
LISTEN_PORT = int(os.environ.get("AEROSENSE_PORT", "5005"))

# REST API (uzaktan erişim)
API_HOST = os.environ.get("AEROSENSE_API_HOST", "0.0.0.0")
# Varsayılan: yüksek port (5000/8000 gibi yaygın çakışmalardan kaçınır). %100 boşluk garantisi yoktur;
# gerekirse AEROSENSE_API_PORT ile değiştirin (ör. 8765, 5000).
_DEFAULT_API_PORT = "38471"
API_PORT = int(os.environ.get("AEROSENSE_API_PORT", _DEFAULT_API_PORT))

# Kanal sırası: vericide tanımlı isimler; yeni sensörler JSON'da gelirse alfabetik eklenir
CHANNEL_ORDER = ["sicaklik", "mq7", "mq135", "toz"]

# Sağlık: (min, max) voltaj veya sıcaklık aralığı — LM35 için sicaklik ~0–50 C varsayımı
CHANNEL_HEALTH_RANGES = {
    "sicaklik": (-10.0, 60.0),
    "mq7": (0.0, 5.0),
    "mq135": (0.0, 5.0),
    "toz": (0.0, 5.0),
}

# Veri bayat sayılması (saniye)
STALE_SECONDS = float(os.environ.get("AEROSENSE_STALE_SEC", "15"))

# Kural tabanlı eşikler (voltaj, LM35 hariç)
THRESHOLDS_MQ7_HIGH = float(os.environ.get("AEROSENSE_MQ7_HIGH", "2.5"))
THRESHOLDS_MQ135_HIGH = float(os.environ.get("AEROSENSE_MQ135_HIGH", "2.5"))
THRESHOLDS_TOZ_HIGH = float(os.environ.get("AEROSENSE_TOZ_HIGH", "2.0"))

# Ses: TTS (konuşma), otomatik uyarı, STT (sesli komut) ayrı ayrı kapatılabilir
def _env_on(key, default="1"):
    return os.environ.get(key, default).lower() not in ("0", "false", "no", "off")


VOICE_ENABLED = _env_on("AEROSENSE_VOICE", "1")  # TTS + otomatik sesli özet (pyttsx3)
VOICE_AUTO_ALERTS = _env_on("AEROSENSE_VOICE_ALERTS", "1")  # AI değişince otomatik ses
VOICE_STT_ENABLED = _env_on("AEROSENSE_VOICE_COMMANDS", "1")  # Mikrofon / sesli komut
VOICE_LANG_HINT = "tr"
# STT: listen(timeout) çok kısaysa konuşma başlamadan süre biter (Windows’ta sık sorun)
VOICE_STT_LISTEN_TIMEOUT = float(os.environ.get("AEROSENSE_STT_TIMEOUT", "8"))
VOICE_STT_PHRASE_LIMIT = float(os.environ.get("AEROSENSE_STT_PHRASE", "14"))
VOICE_STT_ENERGY = int(os.environ.get("AEROSENSE_STT_ENERGY", "280"))

# GUI / panel varsayılan dili: tr | en (AEROSENSE_LANG)

# GUI tam ekran
FULLSCREEN_DEFAULT = os.environ.get("AEROSENSE_FULLSCREEN", "1") not in ("0", "false")

_DEFAULT_LANG = (os.environ.get("AEROSENSE_LANG", "tr") or "tr").lower()[:2]
UI_LANG = "en" if _DEFAULT_LANG == "en" else "tr"
