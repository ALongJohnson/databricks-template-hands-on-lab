#!/usr/bin/env python3
"""Render a workshop spec into the Zensical site sources.

    python scripts/render.py [--workshop workshops/<name>]

Inputs
  workshops/<name>/workshop.yaml   the spec (data, architecture, story, expected results)
  workshops/<name>/images/         screenshots that show this workshop's data (optional)
  workshops/<name>/files/          documents for Step 4.5 (PDFs)
  templates/                       page, lab-file and nav templates (shared by every workshop)
  docs/assets/                     shared CSS, JS, logo, persona avatars and UI-only screenshots

Outputs (generated, git-ignored)
  docs/eng/**.md, docs/eng/assets/, lab-files/eng/**, zensical.eng.toml
  workshops/<name>/SCREENSHOTS_TODO.md   screenshots the pages reference but this workshop lacks
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates"
DOCS_OUT = ROOT / "docs" / "eng"
LAB_OUT = ROOT / "lab-files" / "eng"
SHARED_ASSETS = ROOT / "docs" / "assets"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from spec import load_spec  # noqa: E402


# ---------------------------------------------------------------- filters
def f_num(v):
    if isinstance(v, (int, float)):
        return f"{v:,}"
    return v


def f_poss(name: str) -> str:
    return f"{name}'" if name.endswith("s") else f"{name}'s"


def f_role(title: str) -> str:
    """Lowercase a job title for use mid-sentence, keeping acronyms (AI, BI, ML)."""
    return " ".join(w if w.isupper() and len(w) <= 4 else w.lower() for w in str(title).split())


def f_wbr(name: str) -> str:
    return name.replace("_", "_<wbr>")


def f_code(v) -> str:
    return f"`{v}`"


def f_bold(v) -> str:
    return f"**{v}**"


def f_sq(v: str) -> str:
    return str(v).replace("'", "''")


def f_sqlval(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    return f"'{v}'"


def f_prefix_lines(text: str, prefix: str) -> str:
    return "\n".join((prefix + line).rstrip() for line in str(text).splitlines())


def f_oxford(items) -> str:
    items = list(items)
    if len(items) <= 1:
        return "".join(items)
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


# ---------------------------------------------------------------- helpers
def source_count_sql(spec: dict) -> str:
    mode = spec["architecture"]["mode"]
    parts = []
    for i, src in enumerate(spec["sources"]):
        if mode == "files":
            fmt = src.get("format", spec["architecture"]["files"].get("format", "csv"))
            opts = {**spec["architecture"]["files"].get("options", {}), **src.get("options", {})}
            args = "".join(f", {k} => {f_sqlval(v)}" for k, v in opts.items())
            frm = f"read_files('{src['path']}', format => '{fmt}'{args})"
        else:
            frm = src["ref"]
        if i == 0:
            parts.append(f"SELECT '{src['name']}' AS table_name, count(*) AS row_count FROM {frm}")
        else:
            parts.append(f"SELECT '{src['name']}', count(*) FROM {frm}")
    return "\nUNION ALL\n".join(parts) + ";"


def source_access_permission(spec: dict) -> str:
    mode = spec["architecture"]["mode"]
    if mode == "files":
        root = spec["architecture"]["files"]["root"]
        return "READ VOLUME" if root.startswith("/Volumes/") else "READ FILES"
    if mode == "federation":
        return "USE CATALOG and SELECT on the foreign catalog"
    return ""


class Shots:
    """Resolves screenshot references. A shot renders only if the image exists in the
    shared UI set (docs/assets/images) or in the workshop's own images/ folder."""

    def __init__(self, workshop_dir: Path, extra_dirs: list[Path] | None = None):
        self.dirs = [workshop_dir / "images", *(extra_dirs or []), SHARED_ASSETS / "images"]
        self.missing: dict[str, list[tuple[str, str]]] = {}
        self.page = ""
        self.prefix = "../"

    def __call__(self, rel: str, alt: str) -> str:
        if any((d / rel).is_file() for d in self.dirs):
            return f"![{alt}]({self.prefix}assets/images/{rel})"
        self.missing.setdefault(self.page, []).append((rel, alt))
        return ""


# ---------------------------------------------------------------- main
def build_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
        autoescape=False,
    )
    env.filters.update(role=f_role, num=f_num, poss=f_poss, wbr=f_wbr, code=f_code, bold=f_bold, sq=f_sq,
                       sqlval=f_sqlval, prefix_lines=f_prefix_lines, oxford=f_oxford)
    return env


def build_context(s: dict, shots) -> dict:
    mode = s["architecture"]["mode"]
    return dict(
        s=s,
        mode=mode,
        cat=s["_derived"]["catalog"],
        ex_cat=s["_derived"]["example_catalog"],
        de=s["personas"]["data_engineer"],
        da=s["personas"]["data_analyst"],
        ai=s["personas"]["ai_engineer"],
        bu=s["personas"]["business_user"],
        mv1=s["metric_views"][0],
        mv2=s["metric_views"][1],
        N=s["_derived"]["steps"],
        ds_main=s["dashboard"]["datasets"]["main"] if s["options"]["dashboard"] else None,
        ds_hist=s["dashboard"]["datasets"]["histogram"] if s["options"]["dashboard"] else None,
        ds_bubble=s["dashboard"]["datasets"]["bubble"] if s["options"]["dashboard"] else None,
        t1=s["traps"]["monitoring"],
        t2=s["traps"]["benchmark"],
        warn_rules=s["_derived"]["warn_rules"],
        silver_removed_desc=s["_derived"]["silver_removed_desc"],
        source_count_sql=source_count_sql(s),
        source_access_permission=source_access_permission(s),
        upstream=lambda name: name if mode == "federation" else f"STREAM({name})",
        shot=shots,
    )


def render_lab_files(env: Environment, ctx: dict, out_dir: Path) -> None:
    s = ctx["s"]

    def lab(tpl: str, out_rel: str, **extra):
        text = env.get_template(f"lab-files/{tpl}").render(**ctx, **extra)
        out = out_dir / out_rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text)

    for name in ("bronze", "silver", "gold"):
        lab(f"step1/{name}.sql.j2", f"step1/{name}.sql")
    if s["options"]["dashboard"]:
        for ds in s["dashboard"]["datasets"].values():
            lab("step2/dataset.sql.j2", f"step2/{ds['file']}", ds=ds)
    for mv in s["metric_views"]:
        lab("step3/mv.yaml.j2", f"step3/{mv['name']}.yaml", mv=mv)
    if s["options"]["mcp"]:
        lab("mcp/genie_mcp_agent.py.j2", "mcp/genie_mcp_agent.py")


def render(workshop_dir: Path) -> None:
    s = load_spec(workshop_dir / "workshop.yaml")
    base = (ROOT / "workshops" / s["lab"]["assets_from"]) if s["lab"]["assets_from"] else None
    shots = Shots(workshop_dir, [base / "images"] if base else None)
    env = build_env()
    ctx = build_context(s, shots)
    mode = ctx["mode"]

    # clean generated outputs
    for p in (DOCS_OUT, LAB_OUT):
        if p.exists():
            shutil.rmtree(p)
    DOCS_OUT.mkdir(parents=True)
    LAB_OUT.mkdir(parents=True)

    # pages
    mv1, mv2 = ctx["mv1"], ctx["mv2"]
    page_names = {
        "03-uc-semantics/3-1-mv.md.j2": f"03-uc-semantics/3-1-mv-{mv1['slug']}.md",
        "03-uc-semantics/3-2-mv.md.j2": f"03-uc-semantics/3-2-mv-{mv2['slug']}.md",
    }
    skip = set()
    if not s["options"]["genie_code_pipeline"]:
        skip.add("01-lakeflow-pipeline/1-4-optional-genie-code-vdp.md.j2")
    if not s["options"]["volumes"]:
        skip.add("04-genie-agent/4-5-volumes.md.j2")
    skip_dirs = [d for d, on in (("02-aibi-dashboard/", s["options"]["dashboard"]), ("05-genie-one/", s["options"]["genie_one"]),
                                 ("06-mcp/", s["options"]["mcp"]), ("07-byod/", s["options"]["byod"])) if not on]

    for tpl in sorted((TEMPLATES / "docs").rglob("*.md.j2")):
        rel = tpl.relative_to(TEMPLATES / "docs").as_posix()
        if rel in skip or any(rel.startswith(d) for d in skip_dirs):
            continue
        out_rel = page_names.get(rel, rel[: -len(".j2")])
        shots.page = out_rel
        shots.prefix = "../" * out_rel.count("/")
        text = env.get_template(f"docs/{rel}").render(**ctx)
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)  # collapse gaps left by omitted screenshots
        out = DOCS_OUT / out_rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text)

    # lab files
    render_lab_files(env, ctx, LAB_OUT)

    # nav / site config
    (ROOT / "zensical.eng.toml").write_text(env.get_template("zensical.toml.j2").render(**ctx))

    # assets: shared, then workshop overrides
    assets_out = DOCS_OUT / "assets"
    shutil.copytree(SHARED_ASSETS, assets_out)
    for img_dir in ([base / "images"] if base else []) + [workshop_dir / "images"]:
        if img_dir.is_dir():
            shutil.copytree(img_dir, assets_out / "images", dirs_exist_ok=True)
    (assets_out / "files").mkdir(exist_ok=True)
    if s["options"]["volumes"]:
        for d in s["volume"]["docs"]:
            src = workshop_dir / "files" / d["file"]
            if not src.is_file() and base:
                src = base / "files" / d["file"]
            if not src.is_file():
                raise SystemExit(f"Missing Step 4.5 document: {src} (run scripts/make_documents.py)")
            shutil.copy2(src, assets_out / "files" / d["file"])

    # screenshot report
    lines = ["# Screenshots TODO (generated by scripts/render.py)", "",
             "Pages reference these screenshots, but neither `docs/assets/images/` (shared UI shots)",
             f"nor `{workshop_dir.relative_to(ROOT).as_posix()}/images/` has them, so they are omitted from the site.",
             "Capture each at 2880px wide, mark click targets with a red box, and save it under the",
             "workshop's `images/` folder with the exact path shown.", ""]
    total = 0
    for page, items in shots.missing.items():
        lines.append(f"## {page}")
        lines.append("")
        lines.append("| Path | Shows |")
        lines.append("|---|---|")
        for rel, alt in items:
            lines.append(f"| `{rel}` | {alt} |")
            total += 1
        lines.append("")
    if total == 0:
        lines.append("All referenced screenshots are present.")
    (workshop_dir / "SCREENSHOTS_TODO.md").write_text("\n".join(lines) + "\n")
    print(f"Rendered {workshop_dir.relative_to(ROOT)}: "
          f"{sum(1 for _ in DOCS_OUT.rglob('*.md'))} pages, {total} screenshots missing "
          f"(see {workshop_dir.relative_to(ROOT).as_posix()}/SCREENSHOTS_TODO.md)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workshop", default=os.environ.get("WORKSHOP", "workshops/wanderbricks"))
    args = ap.parse_args()
    wdir = (ROOT / args.workshop).resolve()
    if not (wdir / "workshop.yaml").is_file():
        raise SystemExit(f"No workshop.yaml in {wdir}")
    render(wdir)


if __name__ == "__main__":
    main()
