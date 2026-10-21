"""Produce the Artifact-shaped copy of the report page.

docs/index.html is the canonical page and a complete standalone document,
because GitHub Pages serves it with no wrapper: without a doctype the browser
falls into quirks mode, and without a viewport meta a phone renders it at
desktop width.

The Artifact platform supplies its own <!doctype>/<head>/<body> skeleton and
asks that a published file not carry its own, so this strips exactly those
leading lines back off. One source, two hosts.
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "docs" / "index.html"
DST = ROOT / "out" / "artifact.html"

STRIP = re.compile(r'^\s*(<!doctype html>|<meta charset="utf-8">'
                   r'|<meta name="viewport"[^>]*>)\s*$', re.I)


def main():
    lines = SRC.read_text().splitlines()
    kept = [ln for ln in lines if not STRIP.match(ln)]
    removed = len(lines) - len(kept)
    DST.parent.mkdir(exist_ok=True)
    DST.write_text("\n".join(kept) + "\n")
    print(f"wrote {DST} ({removed} wrapper lines stripped, {len(kept)} kept)")


if __name__ == "__main__":
    main()
