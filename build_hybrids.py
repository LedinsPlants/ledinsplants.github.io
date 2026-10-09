#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bygger hybridsidorna och hybrids-data.js utifrån en tabell.

Tabellerna hämtas från Google Sheets om sheet-url.txt innehåller webbadresser
(en per blad/växtgrupp), annars läses filen hybrids.csv i repot.

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
import os
import re
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
URL_FILE = ROOT / "sheet-url.txt"
TEMPLATE = ROOT / "page-template.html"
DATA_JS = ROOT / "hybrids-data.js"

MARKER = "<!-- auto-generated-hybrid-page -->"
PLACEHOLDER_IMAGE = "https://via.placeholder.com/400x300?text=Hybrid+photo"

# --- Bilder ---------------------------------------------------------------
IMAGE_SLOTS = 6                     # kolumnerna image_1 ... image_6
MAX_MAIN_PX = 1600                  # längsta sida på sidans bilder
MAX_THUMB_PX = 600                  # längsta sida på miniatyren (kortet)
MAX_DOWNLOAD_BYTES = 40 * 1024 * 1024
IMAGES_DIR = ROOT / "images"
IMAGE_MANIFEST = IMAGES_DIR / "drive-sources.json"
# Kan bytas ut med miljövariabeln DRIVE_DOWNLOAD_URL (används vid testning).
DRIVE_DOWNLOAD_URL = os.environ.get(
    "DRIVE_DOWNLOAD_URL", "https://drive.google.com/uc?export=download&id={id}")

WARNINGS = []

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]

# (rubrik på sidan, kolumn i tabellen)
FACT_ROWS = [
    ("Released as", "official_name"),
    ("Working name", "holding_name"),
    ("Parentage", "parentage"),            # byggs av seed_parent/pollen_parent, se build_parentage
    ("Cross pollination", "cross_date"),
    ("Seeds harvested", "seeds_harvested"),
    ("Seeds sown", "seeds_sown"),
    ("First bloom", "first_flowering"),
    ("Produces pollen?", "pollen"),
    ("Flower size", "flower_size"),
    ("Still in cultivation?", "in_cultivation"),
]

NO_VALUES = {"no", "nej", "n", "false", "0"}


def fail(message):
    print(f"\nFEL: {message}", file=sys.stderr)
    sys.exit(1)


def read_sources():
    """Läser sheet-url.txt. Varje rad är antingen en adress eller 'genus = adress'.

    Exempel (ett blad per växtgrupp):
        kohleria  = https://docs.google.com/.../pub?gid=0&single=true&output=csv
        sinningia = https://docs.google.com/.../pub?gid=123&single=true&output=csv

    Etiketten (t.ex. kohleria) används som genus för rader där kolumnen genus
    är tom. Adressen får också vara en filsökväg i repot (t.ex. hybrids.csv).
    """
    sources = []
    if URL_FILE.exists():
        for line in URL_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            match = re.match(r"^([A-Za-z0-9_-]+)\s*=\s*(\S+)$", line)
            if match:
                sources.append((slugify(match.group(1)), match.group(2)))
            else:
                sources.append((None, line.split()[0]))
    return sources


def load_csv_text(location):
    if re.match(r"^https?://", location):
        print(f"Hämtar {location[:70]} ...")
        request = urllib.request.Request(
            location, headers={"User-Agent": "Mozilla/5.0 (hybrid-builder)"})
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
    path = ROOT / location
    if not path.exists():
        fail(f"Hittar inte filen {location}.")
    print(f"Läser {location} ...")
    return path.read_text(encoding="utf-8-sig")


def load_all_rows():
    sources = read_sources() or [(None, "hybrids.csv")]
    rows = []
    for label, location in sources:
        for row in parse_rows(load_csv_text(location)):
            if label and not row.get("genus"):
                row["genus"] = label
            rows.append(row)
    return rows


# Fält där ett inledande ' (sortnamn som 'Pinafore') kan ha försvunnit.
APOSTROPHE_FIELDS = ("name", "official_name", "holding_name", "seed_parent",
                     "pollen_parent", "parentage", "summary")


def restore_leading_apostrophe(row):
    """Google Sheets tolkar ett ' först i en cell som 'det här är text' och
    tar bort det ur värdet, så 'Pinafore' exporteras som Pinafore'. Slutar ett
    värde på ' och har ett udda antal ' är det första citattecknet borta, så
    vi sätter tillbaka det. Returnerar antal rättade fält."""
    fixed = 0
    for field in APOSTROPHE_FIELDS:
        value = row.get(field, "")
        if value.endswith("'") and not value.startswith("'") and value.count("'") % 2 == 1:
            row[field] = "'" + value
            fixed += 1
    return fixed


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
            restore_leading_apostrophe(row)
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


def warn(message):
    WARNINGS.append(message)
    print(f"::warning::{message}")


def drive_file_id(url):
    """Plockar ut fil-id ur en Google Drive-länk, annars None."""
    if "drive.google.com" not in url and "docs.google.com" not in url:
        return None
    match = re.search(r"/d/([A-Za-z0-9_-]{15,})", url) or \
        re.search(r"[?&]id=([A-Za-z0-9_-]{15,})", url)
    return match.group(1) if match else None


def download_drive_file(file_id):
    request = urllib.request.Request(
        DRIVE_DOWNLOAD_URL.format(id=file_id),
        headers={"User-Agent": "Mozilla/5.0 (hybrid-builder)"})
    with urllib.request.urlopen(request, timeout=90) as response:
        content_type = response.headers.get("Content-Type", "")
        data = response.read(MAX_DOWNLOAD_BYTES + 1)
    if len(data) > MAX_DOWNLOAD_BYTES:
        raise ValueError("filen är större än 40 MB")
    if content_type.startswith("text/html") or data[:100].lstrip().lower().startswith(b"<!doctype html"):
        raise ValueError("Google gav en webbsida i stället för bilden. "
                         "Är filen delad med 'Alla med länken'?")
    return data


def save_resized(data, dest, max_px):
    """Sparar en förminskad JPEG utan metadata (inga GPS-uppgifter m.m.)."""
    try:
        from PIL import Image, ImageOps
    except ImportError:
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "pillow", "pillow-heif"])
        from PIL import Image, ImageOps
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
    except Exception:
        pass
    image = Image.open(io.BytesIO(data))
    image = ImageOps.exif_transpose(image)   # rätt rotation innan EXIF slängs
    icc = image.info.get("icc_profile")
    image = image.convert("RGB")
    image.thumbnail((max_px, max_px), Image.LANCZOS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    options = {"quality": 85, "optimize": True, "progressive": True}
    if icc:
        options["icc_profile"] = icc          # färgprofil är ofarlig att behålla
    image.save(dest, "JPEG", **options)       # inget exif= => all metadata utelämnas


def load_manifest():
    if IMAGE_MANIFEST.exists():
        try:
            return json.loads(IMAGE_MANIFEST.read_text(encoding="utf-8"))
        except ValueError:
            pass
    return {}


def image_values(row):
    values = [row.get(f"image_{n}", "") for n in range(1, IMAGE_SLOTS + 1)]
    values = [v for v in values if v]
    if not values:  # äldre kolumner: image + more_images
        values = ([row["image"]] if row.get("image") else []) + split_list(row.get("more_images", ""))
    return values


def prepare_images(row, genus, hybrid_id, manifest):
    """Returnerar [(sida, miniatyr), ...] i samma ordning som kolumnerna.

    Drive-länkar hämtas, förminskas och sparas i images/<genus>hybrids/<id>/.
    Vanliga sökvägar och webbadresser används som de är.
    """
    folder = f"images/{genus}hybrids/{hybrid_id}"
    result, keep = [], set()
    for number, value in enumerate(image_values(row), start=1):
        file_id = drive_file_id(value)
        if not file_id:
            result.append((value, value))
            continue
        main_rel = f"{folder}/{hybrid_id}-{number}.jpg"
        thumb_rel = f"{folder}/{hybrid_id}-{number}-thumb.jpg"
        wanted = [main_rel] + ([thumb_rel] if number == 1 else [])
        keep.update(wanted)
        up_to_date = all((ROOT / rel).exists() and manifest.get(rel) == file_id for rel in wanted)
        if not up_to_date:
            try:
                data = download_drive_file(file_id)
                save_resized(data, ROOT / main_rel, MAX_MAIN_PX)
                if number == 1:
                    save_resized(data, ROOT / thumb_rel, MAX_THUMB_PX)
                for rel in wanted:
                    manifest[rel] = file_id
                print(f"  bild hämtad: {main_rel}")
            except ImportError:
                warn("Pillow saknas, kan inte förminska bilder (pip install pillow).")
                continue
            except Exception as error:
                if all((ROOT / rel).exists() for rel in wanted):
                    print(f"  (behåller tidigare bild för {main_rel})")
                else:
                    warn(f"{hybrid_id}: bild {number} kunde inte hämtas ({error}).")
                    continue
        result.append((main_rel, thumb_rel if number == 1 else main_rel))
    # Städa bort bilder som skapats av skriptet men inte längre används.
    for rel in [r for r in list(manifest) if r.startswith(folder + "/") and r not in keep]:
        path = ROOT / rel
        if path.exists():
            path.unlink()
        del manifest[rel]
    return result


def find_target(raw_id, genus, targets):
    """Hittar sidan för ett id. Accepterar 'id' eller 'genus/id'."""
    parts = [slugify(p) for p in raw_id.split("/") if p.strip()]
    if not parts:
        return None
    if len(parts) >= 2:
        return targets.get(f"{parts[-2]}/{parts[-1]}")
    return targets.get(f"{genus}/{parts[0]}") or targets.get(parts[0])


def build_parentage(row, genus, hybrid_id, own_page, targets, names, links=True):
    """Bygger raden 'Släkte frövärd × pollenförälder' med länkar där id finns.

    Faller tillbaka på kolumnen parentage (fri text) om inga av de nya
    kolumnerna seed_parent / pollen_parent (+ _id) är ifyllda.
    """
    seed, pollen = row.get("seed_parent", ""), row.get("pollen_parent", "")
    seed_id, pollen_id = row.get("seed_parent_id", ""), row.get("pollen_parent_id", "")
    if not (seed or pollen or seed_id or pollen_id):
        return row.get("parentage", "")
    if links and row.get("parentage"):
        print(f"  {hybrid_id}: kolumnen parentage ignoreras eftersom seed/pollen-kolumnerna är ifyllda.")

    def one(text, parent_id, label):
        target = find_target(parent_id, genus, targets) if parent_id else None
        if parent_id and not target and links:
            warn(f"{hybrid_id}: {label} '{parent_id}' hittades inte bland sidorna, så ingen länk skapas.")
        if target == own_page:
            target = None
        if not text and target:
            text = names.get(target) or parent_id
        if not text:
            return "unknown"
        if target and links:
            return f'<a href="/{target}">{text}</a>'
        return text

    prefix = "" if genus == "misc" else f"<i>{genus.capitalize()}</i> "
    return (f"{prefix}{one(seed, seed_id, 'seed_parent_id')} × "
            f"{one(pollen, pollen_id, 'pollen_parent_id')}")


def disk_pages(skip):
    """Alla hybridsidor som ligger i repot (även handgjorda), nyckel 'genus/id' och 'id'."""
    found = {}
    base = ROOT / "hybrids"
    if base.exists():
        for page in sorted(base.rglob("*.html")):
            rel = page.relative_to(ROOT).as_posix()
            if rel in skip:
                continue
            found[f"{page.parent.name}/{page.stem}"] = rel
            found.setdefault(page.stem, rel)
    return found


def build_page(template, row, name, images, parentage=""):
    alt = html.escape(strip_tags(name), quote=True)

    def img_tag(src):
        return (f'<img class="main-photo" src="{html.escape(site_path(src), quote=True)}" '
                f'alt="{alt}">')

    photo = img_tag(images[0][0]) if images else ""

    facts = ""
    values = dict(row, parentage=parentage)
    fact_lines = [f"<tr><th>{label}</th><td>{values[col]}</td></tr>"
                  for label, col in FACT_ROWS if values.get(col)]
    if fact_lines:
        facts = '<table class="facts">\n' + "\n".join(fact_lines) + "\n</table>"

    notes = ""
    if row.get("notes"):
        paragraphs = [p.strip() for p in re.split(r"\r?\n+", row["notes"]) if p.strip()]
        notes = "<h3>Notes</h3>\n" + "\n".join(f"<p>{p}</p>" for p in paragraphs)

    # Övriga bilder staplas under anteckningarna, som på handgjorda sidor.
    gallery = "\n\n".join(img_tag(main) for main, _ in images[1:])

    page = template
    page = page.replace("{{TITLE}}", html.escape(strip_tags(name)) + " – Ledin's Plants")
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

    rows = load_all_rows()
    if not rows:
        fail("Tabellen innehåller inga rader. Avbryter så att inget skrivs över.")

    entries = []
    seen = set()
    manifest = load_manifest()
    written, skipped, removed = [], [], []

    # Steg 1: sortera ut raderna och ta reda på vilka sidor som ska finnas,
    # så att en hybrid kan länka till en annan oavsett ordning i tabellen.
    jobs = []
    for number, row in enumerate(rows, start=2):  # rad 1 är rubrikraden
        hybrid_id = slugify(row.get("id", ""))
        if not hybrid_id:
            print(f"Rad {number}: saknar id, hoppar över.")
            continue
        genus = slugify(row.get("genus", "")) or "misc"
        if not row.get("genus"):
            print(f"Rad {number} ({hybrid_id}): saknar genus, använder 'misc'.")
        key = (genus, hybrid_id)
        if key in seen:
            print(f"Rad {number}: id '{hybrid_id}' används redan inom {genus}, hoppar över.")
            continue
        seen.add(key)
        jobs.append({
            "number": number, "row": row, "id": hybrid_id, "genus": genus,
            "name": row.get("name") or hybrid_id,
            "page_rel": f"hybrids/{genus}/{hybrid_id}.html",
            "hidden": row.get("publish", "").strip().lower() in NO_VALUES,
        })

    targets, names = {}, {}
    to_delete = set()
    for job in jobs:
        page_file = ROOT / job["page_rel"]
        if job["hidden"]:
            if page_file.exists() and MARKER in page_file.read_text(encoding="utf-8"):
                to_delete.add(job["page_rel"])
            continue
        targets[f"{job['genus']}/{job['id']}"] = job["page_rel"]
        targets.setdefault(job["id"], job["page_rel"])
        names[job["page_rel"]] = job["name"]
    for key, rel in disk_pages(to_delete).items():
        targets.setdefault(key, rel)

    # Steg 2: bygg sidorna.
    for job in jobs:
        row, hybrid_id, genus = job["row"], job["id"], job["genus"]
        name, page_rel = job["name"], job["page_rel"]
        page_file = ROOT / page_rel

        if job["hidden"]:
            if page_rel in to_delete:
                page_file.unlink()
                removed.append(page_rel)
            continue

        date = row.get("date", "")
        if date and not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
            print(f"Rad {job['number']} ({hybrid_id}): datumet '{date}' bör skrivas ÅÅÅÅ-MM-DD.")

        summary = row.get("summary", "")
        if not summary:
            plain = build_parentage(row, genus, hybrid_id, page_rel, targets, names, links=False)
            if plain:
                summary = f"Cross between {plain}."

        images = prepare_images(row, genus, hybrid_id, manifest)
        card_image = images[0][1] if images else ""
        entries.append({
            "name": name,
            "date": date,
            "dateDisplay": row.get("date_display") or pretty_date(date),
            "image": site_path(card_image) if card_image else PLACEHOLDER_IMAGE,
            "summary": summary,
            "page": page_rel,
            "genus": genus,
        })

        # Skriv aldrig över handgjorda sidor.
        if page_file.exists() and MARKER not in page_file.read_text(encoding="utf-8"):
            skipped.append(page_rel)
            continue
        parentage = build_parentage(row, genus, hybrid_id, page_rel, targets, names)
        page_file.parent.mkdir(parents=True, exist_ok=True)
        page_file.write_text(build_page(template, row, name, images, parentage), encoding="utf-8")
        written.append(page_rel)

    if manifest or IMAGE_MANIFEST.exists():
        IMAGES_DIR.mkdir(exist_ok=True)
        IMAGE_MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

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
    if WARNINGS:
        print(f"  VARNINGAR: {len(WARNINGS)} (se ovan)")
    if removed:
        print(f"  Sidor borttagna (publish = no): {len(removed)}")
        for p in removed:
            print(f"    - {p}")


if __name__ == "__main__":
    main()
