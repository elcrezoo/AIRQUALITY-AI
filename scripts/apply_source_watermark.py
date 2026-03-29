# -*- coding: utf-8 -*-
# © 2026 Enes Bozkurt — KBU Mekatronik 2026 — https://enesbozkurt.com.tr — Tüm hakları saklıdır.
"""
Kaynak dosyalarina dosya basi filigrani ekler (bir kez calistirin).
"""
from __future__ import print_function

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from aerosense_ai.project_meta import NOTICE_FILE_HEADER  # noqa: E402

MARKER = "Telif (Copyright) © 2026 Enes Bozkurt"


def process_file(path):
    with open(path, "r", encoding="utf-8") as f:
        s = f.read()
    if MARKER in s:
        return False
    if s.startswith("# -*- coding"):
        lines = s.splitlines(True)
        head = lines[0]
        rest = lines[1:]
        if rest and rest[0].strip() == "":
            new = head + "\n" + NOTICE_FILE_HEADER + "\n" + "".join(rest[1:])
        else:
            new = head + "\n" + NOTICE_FILE_HEADER + "\n" + "".join(rest)
    else:
        new = "# -*- coding: utf-8 -*-\n\n" + NOTICE_FILE_HEADER + "\n" + s
    with open(path, "w", encoding="utf-8") as f:
        f.write(new)
    return True


def main():
    n = 0
    for dirpath, dirnames, filenames in os.walk(ROOT):
        if ".git" in dirnames:
            dirnames.remove(".git")
        skip = {"venv", ".venv", "__pycache__", ".mypy_cache"}
        dirnames[:] = [d for d in dirnames if d not in skip]
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            if fn in ("project_meta.py", "apply_source_watermark.py"):
                continue
            full = os.path.join(dirpath, fn)
            if process_file(full):
                print("+", full)
                n += 1
    print("Guncellenen dosya sayisi:", n)


if __name__ == "__main__":
    main()
