#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Håller header, meny och sidfot likadana på ALLA sidor.

Texten i partials/header.html och partials/footer.html är den enda källan.
Skriptet lägger in dem mellan markeringarna

    <!-- header:start ... -->  ...  <!-- header:end -->
    <!-- footer:start ... -->  ...  <!-- footer:end -->

i varje .html-fil. Saknas markeringarna (t.ex. på en sida du kopierat från en
gammal sida) hittar skriptet den gamla headern/sidfoten och lägger dit dem.

Körs automatiskt av GitHub Actions, eller för hand:  python sync_layout.py
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PARTIALS = ROOT / "partials"
SKIP_DIRS = {".git", ".github", "partials", "node_modules"}

NOTE = "skapas av sync_layout.py från partials/{}.html - ändra i den filen, inte här"

# Gamla, omarkerade block som ska "adopteras".
LEGACY = {
    "header": re.compile(r'<header class="site-header">.*?</header>\s*<nav class="main-nav">.*?</nav>', re.S),
    "footer": re.compile(r"<footer>.*?</footer>", re.S),
}


def marked(name):
    return re.compile(
        rf"<!-- {name}:start[^>]*-->.*?<!-- {name}:end -->", re.S)


def block(name, content):
    return (f"<!-- {name}:start ({NOTE.format(name)}) -->\n"
            f"{content.strip()}\n"
            f"<!-- {name}:end -->")


def main():
    parts = {}
    for name in ("header", "footer"):
        path = PARTIALS / f"{name}.html"
        if not path.exists():
            print(f"FEL: {path} saknas.", file=sys.stderr)
            sys.exit(1)
        parts[name] = path.read_text(encoding="utf-8")

    changed, problems = [], []
    for page in sorted(ROOT.rglob("*.html")):
        if SKIP_DIRS & set(page.relative_to(ROOT).parts):
            continue
        text = original = page.read_text(encoding="utf-8")
        rel = page.relative_to(ROOT).as_posix()
        if 'http-equiv="refresh"' in text:   # omdirigeringssidor har ingen layout
            continue
        for name in ("header", "footer"):
            new_block = block(name, parts[name])
            if marked(name).search(text):
                text = marked(name).sub(lambda m: new_block, text, count=1)
            elif LEGACY[name].search(text):
                text = LEGACY[name].sub(lambda m: new_block, text, count=1)
            else:
                problems.append(f"{rel}: hittar ingen {name}")
        if text != original:
            page.write_text(text, encoding="utf-8")
            changed.append(rel)

    print(f"Layout synkad: {len(changed)} sidor ändrade.")
    for rel in changed:
        print(f"  ~ {rel}")
    for problem in problems:
        print(f"::warning::{problem}")


if __name__ == "__main__":
    main()
