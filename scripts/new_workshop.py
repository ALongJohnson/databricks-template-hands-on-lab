#!/usr/bin/env python3
"""Start a new workshop from the reference example.

    python scripts/new_workshop.py <name>

Creates workshops/<name>/ with a copy of the reference spec plus empty images/ and
files/ folders. Every value is still the example's; adapt all of them (or let the
adapt-hands-on-lab Claude skill do it). scripts/validate.py fails while any
example term remains.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REFERENCE = ROOT / "workshops" / "wanderbricks"

HEADER = """# =============================================================================
# Workshop spec: {name}
#
# Copied from workshops/wanderbricks. Replace every value with this workshop's
# data, architecture and story. Field-by-field guidance:
#   .claude/skills/adapt-hands-on-lab/references/spec-reference.md
# Then: scripts/validate.py -> scripts/dryrun.py -> scripts/render.py -> scripts/build.sh
# =============================================================================
"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("name", help="folder name, lowercase-with-dashes (e.g. acme-retail)")
    args = ap.parse_args()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", args.name):
        raise SystemExit("name must be lowercase letters, digits and dashes")
    dest = ROOT / "workshops" / args.name
    if dest.exists():
        raise SystemExit(f"{dest} already exists")
    (dest / "images").mkdir(parents=True)
    (dest / "files").mkdir()
    body = (REFERENCE / "workshop.yaml").read_text()
    body = body[body.index("lab:"):]  # drop the reference header
    (dest / "workshop.yaml").write_text(HEADER.format(name=args.name) + "\n" + body)
    (dest / "images" / ".gitkeep").write_text("")
    (dest / "files" / ".gitkeep").write_text("")
    print(f"Created {dest.relative_to(ROOT)}. Next: edit workshop.yaml, then "
          f"python scripts/validate.py --workshop {dest.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
