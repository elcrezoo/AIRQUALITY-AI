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

import hashlib
import queue
import re
import sys
import threading
import time

from . import config


class VoiceService(object):
    """TTS (pyttsx3), otomatik AI uyarısı, STT (SpeechRecognition) — bağımsız bayraklar."""

    def __init__(self, state, get_ai_summary):
        self.state = state
        self.get_ai_summary = get_ai_summary
        self._q = queue.Queue()
        self._stop = threading.Event()
        self._last_hash = None
        self._worker = None
        self._qt_speak = None  # GUI: ana iş parçacığında QTextToSpeech (Windows’ta güvenilir)
        self._status_lock = threading.Lock()
        self.status = {
            "tts_ready": False,
            "tts_note": "Baslatilmadi",
            "stt_ready": False,
            "stt_note": "Baslatilmadi",
            "last_heard": "-",
            "last_spoke_preview": "-",
        }

    def _set_status(self, **kwargs):
        with self._status_lock:
            self.status.update(kwargs)

    def get_status_copy(self):
        with self._status_lock:
            return dict(self.status)

    def attach_qt_tts(self, speak_fn):
        """
        PyQt ana döngüsünde konuşma (ör. QTextToSpeech). speak_fn(text) herhangi bir iş
        parçacığından güvenle çağrılabilir (sinyal kuyruklanır).
        Windows’ta pyttsx3 arka planda sessiz kalabildiği için GUI açıkken önceliklidir.
        """
        self._qt_speak = speak_fn
        self._set_status(tts_ready=True, tts_note="TTS: Qt Speech (ana is parcacigi)")

    def start(self):
        if config.VOICE_ENABLED:
            self._worker = threading.Thread(
                target=self._run_tts, name="aerosense-tts", daemon=True
            )
            self._worker.start()
        else:
            self._set_status(
                tts_ready=False,
                tts_note="TTS kapali (AEROSENSE_VOICE=0)",
            )
        if config.VOICE_ENABLED and config.VOICE_AUTO_ALERTS:
            threading.Thread(
                target=self._watch_ai_changes,
                name="aerosense-voice-watch",
                daemon=True,
            ).start()
        elif not config.VOICE_AUTO_ALERTS:
            pass
        if config.VOICE_STT_ENABLED:
            self._try_start_stt()
        else:
            self._set_status(stt_ready=False, stt_note="Sesli komut kapali (AEROSENSE_VOICE_COMMANDS=0)")

    def stop(self):
        self._stop.set()
        try:
            self._q.put_nowait(None)
        except Exception:
            pass

    def speak(self, text_tr):
        text_tr = (text_tr or "").strip()
        if not text_tr:
            return
        self._set_status(last_spoke_preview=text_tr[:120] + ("..." if len(text_tr) > 120 else ""))
        if not config.VOICE_ENABLED:
            return
        if self._qt_speak is not None:
            try:
                self._qt_speak(str(text_tr))
                return
            except Exception as e:
                print("[voice] Qt TTS cagri hatasi, pyttsx3 deneniyor: %s" % e)
        try:
            self._q.put(str(text_tr))
        except Exception:
            pass

    def _init_tts_engine(self):
        import pyttsx3 as _ptts

        last_err = None
        if sys.platform == "win32":
            try:
                return _ptts.init("sapi5"), None
            except Exception as e:
                last_err = e
        try:
            return _ptts.init(), last_err
        except Exception as e:
            return None, e

    def _run_tts(self):
        com_inited = False
        if sys.platform == "win32":
            try:
                import ctypes

                ctypes.windll.ole32.CoInitialize(None)
                com_inited = True
            except Exception as e:
                print("[voice] Windows CoInitialize (SAPI): %s" % e)
        try:
            import pyttsx3  # noqa: F401 — _init_tts_engine kullanir
        except ImportError:
            self._set_status(tts_ready=False, tts_note="pyttsx3 yuklu degil (pip install pyttsx3)")
            print("[voice] pyttsx3 yok")
            if com_inited:
                try:
                    import ctypes

                    ctypes.windll.ole32.CoUninitialize()
                except Exception:
                    pass
            return
        engine, err = self._init_tts_engine()
        if engine is None:
            msg = "TTS baslatilamadi: %s" % err
            self._set_status(tts_ready=False, tts_note=msg)
            print("[voice]", msg)
            if com_inited:
                try:
                    import ctypes

                    ctypes.windll.ole32.CoUninitialize()
                except Exception:
                    pass
            return
        try:
            for v in engine.getProperty("voices") or []:
                vn = (v.name or "").lower()
                vid = (v.id or "").lower()
                if "turkish" in vn or "tr" in vid or "turk" in vn:
                    engine.setProperty("voice", v.id)
                    break
        except Exception:
            pass
        engine.setProperty("rate", 172)
        try:
            engine.setProperty("volume", 1.0)
        except Exception:
            pass
        if self._qt_speak is None:
            self._set_status(tts_ready=True, tts_note="Aktif (pyttsx3)")
        while not self._stop.is_set():
            try:
                msg = self._q.get(timeout=0.5)
            except queue.Empty:
                continue
            if msg is None:
                break
            try:
                engine.say(msg)
                engine.runAndWait()
            except Exception as e:
                print("[voice] soyleme hatasi: %s" % e)
                self._set_status(tts_note="Hata: %s" % e)
        if com_inited:
            try:
                import ctypes

                ctypes.windll.ole32.CoUninitialize()
            except Exception:
                pass

    def _watch_ai_changes(self):
        cooldown = 40.0
        last_spoke = 0.0
        while self.state.running and not self._stop.is_set():
            time.sleep(3.5)
            text, _ = self.state.get_ai()
            if not text:
                continue
            h = hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()
            now = time.time()
            if h != self._last_hash and (now - last_spoke) >= cooldown:
                self._last_hash = h
                last_spoke = now
                self.speak(text)

    def _status_utterance_tr(self):
        """Sesli komut cevabı: özet + AQI; boş kalmaz."""
        summary, detail = self.get_ai_summary()
        an = self.state.get_analysis()
        latest, ch_order, ts = self.state.get_latest()
        parts = []
        if summary and summary.strip():
            parts.append(summary.strip())
        if an:
            lvl = an.get("aqi_level", "")
            conf = an.get("confidence", 0)
            adv = (an.get("advice") or "").strip()
            if lvl:
                parts.append("Hava kalitesi: %s." % lvl)
            parts.append("Güven yüzde %s." % conf)
            if adv:
                parts.append(adv[:220])
        elif detail and detail.strip():
            parts.append(detail.strip()[:300])
        if not parts:
            if latest:
                keys = ch_order if ch_order else list(latest.keys())
                bits = []
                for k in keys[:6]:
                    try:
                        bits.append("%s %.4g" % (k, float(latest[k])))
                    except (TypeError, ValueError, KeyError):
                        pass
                if bits:
                    parts.append("Ölçümler: " + ", ".join(bits) + ".")
            if not parts:
                parts.append(
                    "Henüz sensör verisi yok veya bağlantı bekleniyor. "
                    "Verici bağlantısını ve TCP portunu kontrol edin."
                )
        text = " ".join(parts)
        return text[:900]

    @staticmethod
    def _stt_command_match(text):
        """Türkçe / İngilizce tetikleyiciler — kelime bazlı (ör. 'fair' içinde 'air' yanlış tetiklemez)."""
        if not text:
            return False
        low = text.lower()
        for ch in ".,;:!?\"'()[]":
            low = low.replace(ch, " ")
        tokens = set(re.findall(r"[\wçğıöşüÇĞİÖŞÜ]+", low))
        tr_ok = {
            "durum",
            "durumu",
            "hava",
            "kalite",
            "özet",
            "ozet",
            "rapor",
            "aqi",
            "söyle",
            "soyle",
            "nedir",
        }
        en_ok = {
            "status",
            "summary",
            "report",
            "weather",
            "quality",
            "condition",
            "sensor",
            "state",
            "tell",
            "read",
            "air",
        }
        if tokens & tr_ok or tokens & en_ok:
            return True
        if "hava" in tokens and "kalite" in tokens:
            return True
        if "air" in tokens and ("quality" in tokens or "weather" in tokens):
            return True
        return False

    def _recognize_google_multi(self, r, audio):
        import speech_recognition as sr

        last_net = None
        for lang in ("tr-TR", "en-US", "en-GB"):
            try:
                return r.recognize_google(audio, language=lang)
            except sr.UnknownValueError:
                continue
            except sr.RequestError as ex:
                last_net = ex
                break
        if last_net:
            raise last_net
        return None

    def _try_start_stt(self):
        def loop():
            try:
                import speech_recognition as sr
            except ImportError:
                self._set_status(
                    stt_ready=False,
                    stt_note="SpeechRecognition yok (pip install SpeechRecognition)",
                )
                print("[voice] pip install SpeechRecognition pyaudio")
                return
            r = sr.Recognizer()
            r.energy_threshold = max(80, getattr(config, "VOICE_STT_ENERGY", 280))
            r.dynamic_energy_threshold = True
            r.pause_threshold = 0.7
            listen_timeout = max(2.0, float(config.VOICE_STT_LISTEN_TIMEOUT))
            phrase_limit = max(4.0, float(config.VOICE_STT_PHRASE_LIMIT))
            try:
                mic = sr.Microphone()
            except Exception as e:
                self._set_status(stt_ready=False, stt_note="Mikrofon: %s" % e)
                print("[voice] Mikrofon yok:", e)
                return
            self._set_status(
                stt_ready=True,
                stt_note="Dinleniyor (Google STT, TR/EN · timeout %.0fs)" % listen_timeout,
            )
            print(
                "[voice] Sesli komut aktif — '%.0fs' içinde konuşun: durum, hava kalitesi, özet, status…"
                % listen_timeout
            )
            with mic as source:
                try:
                    r.adjust_for_ambient_noise(source, duration=1.0)
                except Exception:
                    pass
            while self.state.running and not self._stop.is_set():
                try:
                    with mic as source:
                        audio = r.listen(
                            source,
                            timeout=listen_timeout,
                            phrase_time_limit=phrase_limit,
                        )
                    try:
                        txt = self._recognize_google_multi(r, audio)
                    except sr.RequestError as ex:
                        self._set_status(stt_note="Ag/STT: %s" % ex)
                        time.sleep(2)
                        continue
                    if not txt:
                        continue
                    self._set_status(last_heard=txt)
                    if not self._stt_command_match(txt):
                        continue
                    utter = self._status_utterance_tr()
                    if config.VOICE_ENABLED:
                        self.speak(utter)
                    else:
                        self._set_status(
                            last_spoke_preview="(TTS kapalı) " + utter[:200]
                        )
                except sr.WaitTimeoutError:
                    continue
                except Exception as e:
                    print("[voice] STT:", e)
                    time.sleep(1.5)

        threading.Thread(target=loop, name="aerosense-stt", daemon=True).start()
