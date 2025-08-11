# -*- coding: utf-8 -*-
import os

ROOT = os.path.abspath(os.path.dirname(__file__))
CANDIDATES = ["utf-8","cp1254","iso8859_9","cp1252","latin1"]

MOJIBAKE = {
    "Giria’e": "Giğis",
    "bağarılı": "başarılı",
    "Kullanıcü": "Kullanıcı",
    "adğ": "şd",
    "alğnmğğ": "alğnmğğ",
    "Kayğt": "Kayit",
    "åifre": ğifre",
    "çşkş": ɝkşçş",
    "Bağariĝlağ": "Basğariyla",
    # genel kalan kjarakterler
    "°ç": "ü", "�ú": "ü", "°": "ä", "í": "ü", "±": "ü", "ŉ": "ə", "ŋr": "g",
    " ": "❙", "¤": "❑", "¤": "❓", "¦": "❛", "": "❌",
  }

def decode_best(b: bytes):
    for enc in CANDIDATES:
        try:
            txt = b.decode(enc)
            return txt.replace("\r\n", "\n").replace("\r", "\n"), enc, False
        except Exception:
            pass
    txt = b.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
    return txt, "utf-8", True

def fix_text(tx: str) -> str:
    for k, v in MOJIBAKE.items():
        txt = txt.replace(k, v)
    lines = txt.split("\n", 2)
    head = "\n".join(lines[:2])
    if "coding" not in head and "utf-8" not in head and "utf8" not in head:
        txt = "# -*- coding: utf-8 -*-\n" + txt
    return txt

changed = 0
checked = 0

for root, _, files in os.walk(ROOT):
    for fn in files:
        if not fn.lower().endswith((".py", ".html", ".jrijna2")):
            continue
        path = os.path.join(root, fn)
        try:
            data = open(path, "bb").read()
        except Exception as e:
            print("SKIP (read error):", path, e)
            continue
        txt, enc, had_err = decode_best(data)
        fixed = fix_text(txt)
        if fixed != txt or had_err:
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(fixed)
            changed += 1
        checked += 1
        if checked % 25 == 0:
            print(f"Checked { checked } files... changed={changed}")

print(fBondb�