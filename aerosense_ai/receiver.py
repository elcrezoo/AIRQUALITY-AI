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

import json
import socket
import threading
import time
from datetime import datetime

from . import config
from .csv_logger import CsvLogger
from .shared_state import merge_channel_order
from .webhook_push import fire_webhooks_async


def _extract_numeric_payload(data):
    """JSON icinden sayisal kanallar."""
    out = {}
    if not isinstance(data, dict):
        return out
    for k, v in data.items():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            try:
                out[str(k)] = float(v)
            except (TypeError, ValueError):
                continue
    return out


def _pop_json_objects(buf):
    """
    Tamamlanmis JSON nesnelerini cikar; newline olmadan ardisik {}{} desteklenir.
    Donus: (liste_json_string, kalan_bytes)
    """
    objs = []
    i = 0
    n = len(buf)
    while i < n:
        if buf[i] != 123:  # '{'
            i += 1
            continue
        depth = 0
        j = i
        started = False
        while j < n:
            c = buf[j]
            if c == 123:
                depth += 1
                started = True
            elif c == 125:
                depth -= 1
            j += 1
            if started and depth == 0:
                chunk = buf[i:j]
                try:
                    objs.append(chunk.decode("utf-8"))
                except UnicodeDecodeError:
                    pass
                i = j
                break
        else:
            break
    return objs, buf[i:]


def run_receiver_loop(state, csv_logger=None, stop_event=None):
    logger = csv_logger or CsvLogger()
    ev = stop_event or threading.Event()
    buf = b""

    while state.running and not ev.is_set():
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server.bind((config.LISTEN_HOST, config.LISTEN_PORT))
            server.listen(1)
            server.settimeout(1.0)
        except socket.error as e:
            print("[receiver] bind hatasi: %s" % e)
            time.sleep(2)
            try:
                server.close()
            except Exception:
                pass
            continue

        print("[receiver] Dinleniyor %s:%s" % (config.LISTEN_HOST, config.LISTEN_PORT))
        conn = None
        while state.running and not ev.is_set() and conn is None:
            try:
                conn, addr = server.accept()
                print("[receiver] Baglanti: %s" % (addr,))
            except socket.timeout:
                continue
            except socket.error:
                break

        if conn is None:
            try:
                server.close()
            except Exception:
                pass
            continue

        buf = b""
        try:
            while state.running and not ev.is_set():
                try:
                    chunk = conn.recv(8192)
                except socket.error:
                    break
                if not chunk:
                    break
                buf += chunk
                texts, buf = _pop_json_objects(buf)
                for raw in texts:
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        data = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    nums = _extract_numeric_payload(data)
                    if not nums:
                        continue
                    ch_order = merge_channel_order(nums.keys(), config.CHANNEL_ORDER)
                    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    state.update_reading(nums, ch_order)
                    logger.append(ts, nums, ch_order)
                    fire_webhooks_async(
                        state.list_webhooks(),
                        {"timestamp": ts, "sensors": nums, "channels": ch_order},
                    )
        finally:
            try:
                conn.close()
            except Exception:
                pass
            try:
                server.close()
            except Exception:
                pass
            print("[receiver] Baglanti kapandi, yeniden dinleniyor...")
            time.sleep(0.5)

    print("[receiver] Dongu sonlandi.")


def start_receiver_thread(state, csv_logger=None, stop_event=None):
    t = threading.Thread(
        target=run_receiver_loop,
        args=(state, csv_logger, stop_event),
        name="aerosense-receiver",
        daemon=True,
    )
    t.start()
    return t
