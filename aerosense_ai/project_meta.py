# -*- coding: utf-8 -*-
# Proje kimliği — © 2026 Enes Bozkurt | KBU Mekatronik Mühendisliği 2026 | enesbozkurt.com.tr
"""
Proje kimligi, filigran ve telif metinleri (tek dogruluk kaynagi).
"""

PROJECT_NAME = "AeroSense AI"
VERSION = "2.0.0-stable"

AUTHOR = "Enes Bozkurt"
AFFILIATION = "Karabük Üniversitesi (KBU) — Mekatronik Mühendisliği — 2026"
WEBSITE = "https://enesbozkurt.com.tr"

COPYRIGHT_LINE = "Copyright © 2026 Enes Bozkurt. Tüm hakları saklıdır."

LEGAL_SHORT = (
    "Bu yazılım ve dokümantasyon, yazarın yazılı izni olmadan çoğaltılamaz, "
    "dağıtılamaz, kiralanamaz veya üçüncü kişilere devredilemez. "
    "Ticari kullanım yasaktır. Akademik çalışmalarda kaynak gösterilmesi zorunludur."
)

NOTICE_ONE_LINE = (
    "AeroSense AI © 2026 Enes Bozkurt | KBU Mekatronik 2026 | enesbozkurt.com.tr"
)

NOTICE_GUI_FOOTER = (
    "© 2026 Enes Bozkurt · KBU Mekatronik Mühendisliği 2026 · enesbozkurt.com.tr · "
    "Tüm hakları saklıdır."
)

NOTICE_FILE_HEADER = """# ==============================================================================
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
"""


def api_notice_dict():
    return {
        "project": PROJECT_NAME,
        "version": VERSION,
        "author": AUTHOR,
        "affiliation": AFFILIATION,
        "website": WEBSITE,
        "copyright": COPYRIGHT_LINE,
        "legal": LEGAL_SHORT,
    }
