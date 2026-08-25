#!/usr/bin/env python3
"""
inberlinwohnen Wohnungswaechter
Ruft den Wohnungsfinder ab, filtert nach eigenen Kriterien und meldet
nur neue Angebote per Telegram oder ntfy.
"""

import json
import os
import re
import sys
import pathlib

import requests
from bs4 import BeautifulSoup

# ----------------------------------------------------------------------
# DEINE FILTER  (hier anpassen)
# ----------------------------------------------------------------------

# Einmaliger Test: meldet ALLE passenden Wohnungen, egal ob schon gesehen.
# Damit pruefst du, ob die Push-Nachricht wirklich ankommt.
# Nach dem Test wieder auf False stellen. Die Merkliste bleibt unberuehrt.
TESTLAUF = False

# Ganz Berlin durchsuchen? Dann bleibt der Ortsfilter komplett aus.
GANZ_BERLIN = True

# Nur relevant, wenn GANZ_BERLIN = False:
BEZIRKE = []
PLZ_FILTER = []

# Reine Beschriftung: taucht in der Push-Nachricht auf, filtert nichts.
PLZ_NAMEN = {
    "12435": "Alt-Treptow / Plaenterwald",
    "12437": "Baumschulenweg",
    "12439": "Niederschoeneweide",
    "12459": "Oberschoeneweide",
    "12487": "Johannisthal",
    "12489": "Adlershof",
    "10405": "Prenzlauer Berg", "10407": "Prenzlauer Berg",
    "10409": "Prenzlauer Berg", "10435": "Prenzlauer Berg",
    "10437": "Prenzlauer Berg", "10439": "Prenzlauer Berg",
    "13086": "Weissensee", "13088": "Weissensee",
}

ZIMMER_MIN = 1.5
ZIMMER_MAX = 2.0
KALTMIETE_MAX = 500.0      # Euro
GESAMTMIETE_MAX = 0        # 0 = egal, Kaltmiete ist die harte Grenze
FLAECHE_MIN = 0            # m2, 0 = keine Untergrenze
FLAECHE_MAX = 50.0         # m2

# ----------------------------------------------------------------------

URL = "https://www.inberlinwohnen.de/wohnungsfinder"
STATE_FILE = pathlib.Path(__file__).parent / "seen.json"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " \
     "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"


def norm(s):
    """Umlaute vereinheitlichen, damit Bezirksnamen zuverlaessig matchen."""
    return (s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
             .replace("Ä", "Ae").replace("Ö", "Oe").replace("Ü", "Ue")
             .replace("ß", "ss"))


def zahl(text, feld):
    """Zahlenwert eines Feldes aus dem Textblock ziehen (deutsches Format)."""
    m = re.search(rf"{feld}:\s*([\d.]+,?\d*)", text)
    if not m:
        return None
    roh = m.group(1).replace(".", "").replace(",", ".")
    try:
        return float(roh)
    except ValueError:
        return None


def text_feld(text, feld):
    m = re.search(rf"{feld}:\s*(.+)", text)
    return m.group(1).strip() if m else ""


def parse(html):
    """Alle Angebote aus der Seite lesen."""
    soup = BeautifulSoup(html, "html.parser")
    treffer = []

    # Der Expose-Link ist der stabilste Anker auf der Seite.
    links = soup.find_all("a", title=re.compile("Expos", re.I))

    for a in links:
        href = a.get("href", "")
        if not href.startswith("http"):
            continue

        # Vom Link aus nach oben laufen, bis der Block alle Daten enthaelt.
        block = a
        for _ in range(10):
            if block.parent is None:
                break
            block = block.parent
            if "Eingestellt am" in block.get_text():
                break
        else:
            continue

        txt = re.sub(r"[ \t]+", " ", block.get_text("\n"))
        if "Eingestellt am" not in txt:
            continue

        treffer.append({
            "id": href,
            "adresse": text_feld(txt, "Adresse"),
            "zimmer": zahl(txt, "Zimmeranzahl"),
            "flaeche": zahl(txt, "Wohnfl.che"),
            "kalt": zahl(txt, "Kaltmiete"),
            "gesamt": zahl(txt, "Gesamtmiete"),
            "wbs": text_feld(txt, "WBS"),
            "eingestellt": text_feld(txt, "Eingestellt am"),
            "url": href,
        })

    # Doppelte Treffer entfernen, falls ein Block mehrere Links enthaelt.
    einmalig = {}
    for t in treffer:
        einmalig.setdefault(t["id"], t)
    return list(einmalig.values())


def lage(w):
    """Ortsteil zur PLZ, nur fuer die Beschriftung."""
    m = re.search(r"\b(\d{5})\b", w["adresse"])
    return PLZ_NAMEN.get(m.group(1)) if m else None


def passt(w):
    if not w["adresse"]:
        return False

    if not GANZ_BERLIN:
        adr = norm(w["adresse"])
        plz = re.search(r"\b(\d{5})\b", w["adresse"])
        im_bezirk = any(norm(b) in adr for b in BEZIRKE)
        im_plz = bool(plz) and plz.group(1) in PLZ_FILTER
        if not (im_bezirk or im_plz):
            return False

    if w["zimmer"] is not None and not (ZIMMER_MIN <= w["zimmer"] <= ZIMMER_MAX):
        return False
    if w["flaeche"] is not None:
        if FLAECHE_MIN and w["flaeche"] < FLAECHE_MIN:
            return False
        if FLAECHE_MAX and w["flaeche"] > FLAECHE_MAX:
            return False
    if w["kalt"] is not None and KALTMIETE_MAX and w["kalt"] > KALTMIETE_MAX:
        return False
    if w["gesamt"] is not None and GESAMTMIETE_MAX and w["gesamt"] > GESAMTMIETE_MAX:
        return False
    return True


def melde(wohnungen):
    zeilen = []
    for w in wohnungen:
        ort = lage(w)
        kopf = f"{w['adresse']}" + (f"  ({ort})" if ort else "")
        zeilen.append(
            f"🏠 {kopf}\n"
            f"{w['zimmer'] or '?'} Zi · {w['flaeche'] or '?'} m² · "
            f"{w['kalt'] or '?'} € kalt · {w['gesamt'] or '?'} € warm\n"
            f"WBS: {w['wbs'] or 'unbekannt'}\n"
            f"{w['url']}"
        )
    text = "NEUE WOHNUNG\n\n" + "\n\n———\n\n".join(zeilen)

    tg_token = os.environ.get("TELEGRAM_TOKEN")
    tg_chat = os.environ.get("TELEGRAM_CHAT_ID")
    ntfy = os.environ.get("NTFY_TOPIC")
    gesendet = False

    if tg_token and tg_chat:
        r = requests.post(
            f"https://api.telegram.org/bot{tg_token}/sendMessage",
            data={"chat_id": tg_chat, "text": text,
                  "disable_web_page_preview": False},
            timeout=20,
        )
        print("Telegram:", r.status_code)
        gesendet = r.ok

    if ntfy:
        r = requests.post(
            f"https://ntfy.sh/{ntfy}",
            data=text.encode("utf-8"),
            headers={"Title": "Neue Wohnung", "Priority": "high",
                     "Tags": "house"},
            timeout=20,
        )
        print("ntfy:", r.status_code)
        gesendet = gesendet or r.ok

    if not gesendet:
        print("Kein Versandkanal konfiguriert. Ausgabe:\n", text)


def main():
    try:
        html = requests.get(URL, headers={"User-Agent": UA}, timeout=30).text
    except Exception as e:
        print("Abruf fehlgeschlagen:", e)
        return 1

    alle = parse(html)
    print(f"{len(alle)} Angebote auf der Seite gefunden")
    if not alle:
        print("WARNUNG: nichts geparst. Struktur der Seite hat sich geaendert.")
        return 1

    gesehen = set()
    if STATE_FILE.exists():
        gesehen = set(json.loads(STATE_FILE.read_text()))

    passend = [w for w in alle if passt(w)]
    print(f"{len(passend)} davon passen zu deinen Filtern")

    if TESTLAUF:
        print("TESTLAUF aktiv: melde alle passenden Wohnungen, "
              "die Merkliste wird nicht veraendert.")
        if passend:
            melde(passend)
        else:
            print("Gerade passt keine einzige Wohnung. Setz KALTMIETE_MAX "
                  "kurzzeitig auf 3000, dann kommt garantiert etwas.")
        return 0

    neu = [w for w in passend if w["id"] not in gesehen]

    erstlauf = not STATE_FILE.exists()
    if neu and not erstlauf:
        melde(neu)
        for w in neu:
            print("NEU:", w["adresse"], w["kalt"], "EUR")
    elif erstlauf:
        print("Erstlauf: Bestand wird nur gespeichert, keine Meldung.")
    else:
        print("Nichts Neues.")

    # Alles Gesehene merken, nicht nur die passenden.
    STATE_FILE.write_text(json.dumps(
        sorted(gesehen | {w["id"] for w in alle}), indent=0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
