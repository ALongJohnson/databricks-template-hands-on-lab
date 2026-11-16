#!/usr/bin/env python3
"""Build the Step 4.5 PDF documents from markdown in the workshop spec.

    python scripts/make_documents.py --workshop workshops/<name> [--force]

Each entry in `volume.docs` needs `file` (the PDF name) and, to be generated,
`title` and `source` (markdown: #/## headings, paragraphs, - bullets, | pipe | tables |).
Existing PDFs are kept unless --force. Requires: pip install fpdf2
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from spec import load_spec  # noqa: E402

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "C:/Windows/Fonts/arial.ttf",
]
ASCII = {"\u2013": "-", "\u2014": "-", "\u2192": "->", "\u2264": "<=", "\u2265": ">=", "\u00d7": "x",
         "\u201c": '"', "\u201d": '"', "\u2019": "'", "\u2022": "-"}


def make_pdf(title: str, source: str, out: Path) -> None:
    from fpdf import FPDF

    pdf = FPDF(format="A4")
    pdf.set_margins(20, 20, 20)
    pdf.set_auto_page_break(True, 20)
    font = next((f for f in FONT_CANDIDATES if Path(f).is_file()), None)
    if font:
        pdf.add_font("Body", "", font)
        pdf.add_font("Body", "B", font)
        family = "Body"
        clean = lambda t: t  # noqa: E731
    else:
        family = "Helvetica"
        clean = lambda t: "".join(ASCII.get(ch, ch) for ch in t).encode("latin-1", "replace").decode("latin-1")  # noqa: E731
    pdf.add_page()
    pdf.set_fill_color(255, 54, 33)
    pdf.rect(0, 0, 210, 6, "F")
    pdf.set_fill_color(255, 255, 255)
    pdf.set_font(family, "B", 18)
    pdf.multi_cell(0, 9, clean(title), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    lines = source.strip().splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(set(c) <= {"-", ":"} for c in cells):
                    rows.append([clean(c.replace("**", "")) for c in cells])
                i += 1
            pdf.set_font(family, "", 10)
            with pdf.table(first_row_as_headings=True, line_height=6, cell_fill_color=(245, 243, 240), cell_fill_mode="ROWS") as table:
                for r in rows:
                    row = table.row()
                    for c in r:
                        row.cell(c)
            pdf.ln(3)
            continue
        if line.startswith("## "):
            pdf.ln(2)
            pdf.set_font(family, "B", 13)
            pdf.multi_cell(0, 7, clean(line[3:]), new_x="LMARGIN", new_y="NEXT")
        elif line.startswith("# "):
            pdf.set_font(family, "B", 15)
            pdf.multi_cell(0, 8, clean(line[2:]), new_x="LMARGIN", new_y="NEXT")
        elif line.startswith("- "):
            pdf.set_font(family, "", 11)
            pdf.multi_cell(0, 6, clean("  - " + line[2:].replace("**", "")), new_x="LMARGIN", new_y="NEXT")
        elif line.strip():
            pdf.set_font(family, "", 11)
            pdf.multi_cell(0, 6, clean(line.replace("**", "")), new_x="LMARGIN", new_y="NEXT")
        else:
            pdf.ln(2)
        i += 1
    out.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(out))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workshop", default=os.environ.get("WORKSHOP", "workshops/wanderbricks"))
    ap.add_argument("--force", action="store_true", help="rebuild PDFs that already exist")
    args = ap.parse_args()
    wdir = (ROOT / args.workshop).resolve()
    s = load_spec(wdir / "workshop.yaml")
    for d in s["volume"]["docs"]:
        out = wdir / "files" / d["file"]
        if out.is_file() and not args.force:
            print(f"keep   {out.relative_to(ROOT)}")
            continue
        if not d.get("source"):
            raise SystemExit(f"volume.docs[{d['file']}] has no `source` markdown to build from")
        make_pdf(d.get("title", d["file"]), d["source"], out)
        print(f"built  {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
