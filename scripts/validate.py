#!/usr/bin/env python3
"""Check a workshop spec against the lab contract (same outputs as the reference lab).

    python scripts/validate.py [--workshop workshops/<name>]

Exit code 1 on errors. For any workshop other than the reference example, leftover
example terms (Wanderbricks, jiyu, ...) are errors, so a copied spec cannot ship
half-adapted.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from spec import validate  # noqa: E402

REFERENCE = "wanderbricks"
REFERENCE_TERMS = ["Wanderbricks", "jiyu", "Summer Escape"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workshop", default=os.environ.get("WORKSHOP", "workshops/wanderbricks"))
    args = ap.parse_args()
    wdir = (ROOT / args.workshop).resolve()
    import yaml
    allow = (yaml.safe_load((wdir / "workshop.yaml").read_text()).get("lab") or {}).get("allow_reference_terms", False)
    forbid = [] if wdir.name == REFERENCE or allow else REFERENCE_TERMS
    if allow and wdir.name != REFERENCE:
        print("WARN  lab.allow_reference_terms is true: reference (Wanderbricks) terms are allowed; set false once the data changes")
    errors, warns = validate(wdir / "workshop.yaml", forbid=forbid)
    for w in warns:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")
    print(f"{wdir.relative_to(ROOT)}: {len(errors)} error(s), {len(warns)} warning(s)")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
