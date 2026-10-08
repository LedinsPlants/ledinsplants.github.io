#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bygger hybridsidorna och hybrids-data.js utifrån en tabell.

Tabellen hämtas från Google Sheets om sheet-url.txt innehåller en webbadress,
annars läses filen hybrids.csv i repot.

Skriptet körs automatiskt av GitHub Actions (se .github/workflows/build.yml),
men kan också köras för hand:  python build_hybrids.py

Säkerhetsspärrar:
  * Skriptet skriver ALDRIG över en sida som saknar markören
    <!-- auto-generated-hybrid-page --> (dvs. sidor du gjort för hand).
  * Går något fel (tabellen går inte att hämta, är tom osv.) avbryts körningen
    innan några filer ändras.
"""

import csv
import html
import io
import json
import re
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOCAL_CSV = ROOT / "hybrids.csv"
URL_FILE = ROOT / "sheet-url.txt"
TEMPLATE = ROOT / "page-template.html"
DATA_JS = ROOT / "hybrids-data.js"

MARKER = "<!-- auto-generated-hybrid-page -->"
PLACEHOLDER_IMAGE = "https://via.placeholder.com/400x300?text=Hybrid+photo"

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]

# (rubrik på sidan, kolumn i tabellen)
FACT_ROWS = [
    ("Official name", "official_name"),
    ("Holding name", "holding_name"),
    ("Parentage", "parentage"),
    ("Cross pollination", "cross_date"),
    ("Seeds harvested", "seeds_harvested"),
    ("Seeds sown", "seeds_sown"),
    ("First flowering", "first_flowering"),
    ("Pollen", "pollen"),
    ("Flower size", "flower_size"),
]

NO_VALUES = {"no", "nej", "n", "false", "0"}


def fail(message):
    print(f"\nFEL: {message}", file=sys.stderr)
    sys.exit(1)


def sheet_url():
    if not URL_FILE.exists():
        return None
    for line in URL_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return line
    return None


def load_csv_text():
    url = sheet_url()
    if url:
        print("Hämtar tabellen från Google Sheets ...")
        request = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 (hybrid-builder)"})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                text = response.read().decode("utf-8-sig")
        except Exception as error:  # nätverksfel, 404 osv.
            fail(f"Kunde inte hämta tabellen ({error}). "
                 "Kontrollera adressen i sheet-url.txt.")
        if re.match(r"\s*<(!doctype|html)", text[:200], re.IGNORECASE):
            fail("Adressen gav en webbsida i stället för en CSV-fil. "
                 "Har du valt Publicera på webben -> CSV i Google Sheets?")
        return text
    if LOCAL_CSV.exists():
        print("Läser hybrids.csv ...")
        return LOCAL_CSV.read_text(encoding="utf-8-sig")
    fail("Hittar varken en adress i sheet-url.txt eller filen hybrids.csv.")


def parse_rows(text):
    reader = csv.DictReader(io.StringIO(text))
    rows = []
    for raw in reader:
        row = {}
        for key, value in raw.items():
            if not key:
                continue
            row[key.strip().lower()] = (value or "").strip()
        if any(row.values()):
            rows.append(row)
    return rows


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def strip_tags(text):
    return re.sub(r"<[^>]+>", "", text)


def pretty_date(iso):
    try:
        d = datetime.strptime(iso, "%Y-%m-%d")
    except ValueError:
        return iso
    return f"{MONTHS[d.month - 1]} {d.day}, {d.year}"


def site_path(path):
    """Gör bildsökvägar absoluta så att de fungerar från undermappar."""
    if re.match(r"^(https?:)?//", path) or path.startswith("/"):
        return path
    return "/" + path


def split_list(text):
    return [p.strip() for p in re.split(r"[;\n]+", text) if p.strip()]


def build_page(template, row, name, image):
    alt = html.escape(strip_tags(name), quote=True)

    photo = ""
    if image:
        photo = (f'<img class="main-photo" src="{html.escape(site_path(image), quote=True)}" '
                 f'alt="{alt}">')

    facts = ""
    fact_lines = [f"<tr><th>{label}</th><td>{row[col]}</td></tr>"
                  for label, col in FACT_ROWS if row.get(col)]
    if fact_lines:
        facts = '<table class="facts">\n' + "\n".join(fact_lines) + "\n</table>"

    notes = ""
    if row.get("notes"):
        paragraphs = [p.strip() for p in re.split(r"\r?\n+", row["notes"]) if p.strip()]
        notes = "<h3>Notes</h3>\n" + "\n".join(f"<p>{p}</p>" for p in paragraphs)

    gallery = ""
    extra = split_list(row.get("more_images", ""))
    if extra:
        imgs = "\n".join(
            f'<img src="{html.escape(site_path(p), quote=True)}" alt="{alt}" '
            f'style="max-width:32%;height:auto;margin:0 0.5%;">'
            for p in extra)
        gallery = f'<div class="gallery">\n{imgs}\n</div>'

    page = template
    page = page.replace("{{TITLE}}", html.escape(strip_tags(name)) + " – My Hybrid Plants")
    page = page.replace("{{NAME}}", name)
    page = page.replace("{{PHOTO}}", photo)
    page = page.replace("{{FACTS}}", facts)
    page = page.replace("{{NOTES}}", notes)
    page = page.replace("{{GALLERY}}", gallery)
    return page


def main():
    if not TEMPLATE.exists():
        fail("Filen page-template.html saknas.")
    template = TEMPLATE.read_text(encoding="utf-8")
    if MARKER not in template:
        fail(f"page-template.html måste innehålla raden {MARKER}")

    rows = parse_rows(load_csv_text())
    if not rows:
        fail("Tabellen innehåller inga rader. Avbryter så att inget skrivs över.")

    entries = []
    seen = set()
    written, skipped, removed = [], [], []

    for number, row in enumerate(rows, start=2):  # rad 1 är rubrikraden
        hybrid_id = slugify(row.get("id", ""))
        if not hybrid_id:
            print(f"Rad {number}: saknar id, hoppar över.")
            continue
        name = row.get("name") or hybrid_id
        genus = slugify(row.get("genus", "")) or "misc"
        if not row.get("genus"):
            print(f"Rad {number} ({hybrid_id}): saknar genus, använder 'misc'.")

        key = (genus, hybrid_id)
        if key in seen:
            print(f"Rad {number}: id '{hybrid_id}' används redan inom {genus}, hoppar över.")
            continue
        seen.add(key)

        page_rel = f"hybrids/{genus}/{hybrid_id}.html"
        page_file = ROOT / page_rel
        hidden = row.get("publish", "").strip().lower() in NO_VALUES

        if hidden:
            if page_file.exists() and MARKER in page_file.read_text(encoding="utf-8"):
                page_file.unlink()
                removed.append(page_rel)
            continue

        date = row.get("date", "")
        if date and not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
            print(f"Rad {number} ({hybrid_id}): datumet '{date}' bör skrivas ÅÅÅÅ-MM-DD.")

        summary = row.get("summary", "")
        if not summary and row.get("parentage"):
            summary = f"Cross between {row['parentage']}."

        image = row.get("image", "")
        entries.append({
            "name": name,
            "date": date,
            "dateDisplay": row.get("date_display") or pretty_date(date),
            "image": image or PLACEHOLDER_IMAGE,
            "summary": summary,
            "page": page_rel,
            "genus": genus,
        })

        # Skriv aldrig över handgjorda sidor.
        if page_file.exists() and MARKER not in page_file.read_text(encoding="utf-8"):
            skipped.append(page_rel)
            continue
        page_file.parent.mkdir(parents=True, exist_ok=True)
        page_file.write_text(build_page(template, row, name, image), encoding="utf-8")
        written.append(page_rel)

    # Nyaste först; vid lika datum behålls ordningen från tabellen.
    entries.sort(key=lambda e: e["date"], reverse=True)

    header = (
        "// ===========================================================\n"
        "// HYBRID DATA - AUTOGENERERAD. REDIGERA INTE DENNA FIL.\n"
        "// Ändra i tabellen (Google Sheets / hybrids.csv) i stället.\n"
        "// Filen skrivs om av build_hybrids.py.\n"
        "// ===========================================================\n\n"
    )
    DATA_JS.write_text(
        header + "const hybrids = " + json.dumps(entries, indent=2) + ";\n",
        encoding="utf-8")

    print(f"\nKlart: {len(entries)} hybrider i hybrids-data.js")
    print(f"  Sidor skapade/uppdaterade: {len(written)}")
    for p in written:
        print(f"    + {p}")
    if skipped:
        print(f"  Handgjorda sidor som lämnades orörda: {len(skipped)}")
        for p in skipped:
            print(f"    = {p}")
    if removed:
        print(f"  Sidor borttagna (publish = no): {len(removed)}")
        for p in removed:
            print(f"    - {p}")


if __name__ == "__main__":
    main()
