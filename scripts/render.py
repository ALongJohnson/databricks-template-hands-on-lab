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


def f_dq(v: str) -> str:
    return str(v).replace("\\", "\\\\").replace('"', '\\"')


def f_to_yaml(v) -> str:
    return yaml.safe_dump(v, sort_keys=False, allow_unicode=True, default_flow_style=False).rstrip()


def f_dbt_refs(sql: str, s: dict) -> str:
    """Point bare Silver table names at dbt refs so dbt builds the lineage; drop the trailing semicolon."""
    for src in s["sources"]:
        t = src["silver"]["table"]
        sql = re.sub(rf"(?<![\w.`]){re.escape(t)}(?![\w`])", "{{ ref('" + t + "') }}", sql)
    return sql.rstrip().rstrip(";")


def f_dbt_test_count(tests) -> int:
    return sum(len(t.get("tests", [])) for t in (tests or []))


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
            opts = src["options"] if "options" in src else spec["architecture"]["files"].get("options", {})
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


STEP1 = {
    "sdp": {
        "title": "Build a Lakeflow Pipeline",
        "desc": "Implement streaming ingestion, data quality checks (Expectations), and incremental processing declaratively with just a few lines of SQL.",
        "tags": ["Lakeflow Spark Declarative Pipelines"],
        "flow": "Lakeflow Pipeline",
        "arch_label": "Lakeflow pipeline",
        "bronze": "Ingest source data",
        "silver": "Cleanse and check quality",
        "built": "Lakeflow pipeline, 7 Bronze, Silver, and Gold tables",
        "highlight": "**Declarative pipelines:** Implemented data collection, quality validation, and incremental processing with just a few lines of SQL.",
    },
    "dbt": {
        "title": "Build a Lakeflow Job with dbt",
        "desc": "Ingest files incrementally with Auto Loader, transform Bronze to Gold with dbt Core models and tests, and orchestrate it all as a Lakeflow Job.",
        "tags": ["Lakeflow Jobs", "dbt Core", "Auto Loader"],
        "flow": "Lakeflow Job · dbt",
        "arch_label": "Lakeflow Job · dbt Core",
        "bronze": "Auto Loader streaming tables",
        "silver": "dbt models + tests",
        "built": "Lakeflow Job running dbt Core, 7 Bronze, Silver, and Gold tables",
        "highlight": "**dbt on Lakeflow Jobs:** Ingested landing-zone files with Auto Loader and turned them into tested, documented tables with dbt Core, orchestrated as a Lakeflow Job.",
    },
}


def dbt_where(constraints) -> str:
    """WHERE clause equivalent of the drop/fail Expectations (warn rules become dbt tests)."""
    conds = [c["expr"] for c in constraints if c.get("action", "drop") != "warn"]
    return "\n  and ".join(f"({c})" for c in conds)


class Shots:
    """Resolves screenshot references. A shot renders only if the image exists in the
    shared UI set (docs/assets/images) or in the workshop's own images/ folder."""

    def __init__(self, workshop_dir: Path, inherit: str = "", exclude=()):
        self.dirs = [workshop_dir / "images", SHARED_ASSETS / "images"]
        self.inherit_dir = ROOT / inherit / "images" if inherit else None
        self.exclude = set(exclude or ())
        self.missing: dict[str, list[tuple[str, str]]] = {}
        self.page = ""
        self.prefix = "../"

    def __call__(self, rel: str, alt: str) -> str:
        dirs = list(self.dirs)
        if self.inherit_dir and rel not in self.exclude:
            dirs.append(self.inherit_dir)
        if any((d / rel).is_file() for d in dirs):
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
                       sqlval=f_sqlval, prefix_lines=f_prefix_lines, oxford=f_oxford,
                       dq=f_dq, to_yaml=f_to_yaml, dbt_refs=f_dbt_refs, dbt_test_count=f_dbt_test_count)
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
        ds_main=s["dashboard"]["datasets"]["main"],
        ds_hist=s["dashboard"]["datasets"]["histogram"],
        ds_bubble=s["dashboard"]["datasets"]["bubble"],
        t1=s["traps"]["monitoring"],
        t2=s["traps"]["benchmark"],
        warn_rules=s["_derived"]["warn_rules"],
        silver_removed_desc=s["_derived"]["silver_removed_desc"],
        source_count_sql=source_count_sql(s),
        source_access_permission=source_access_permission(s),
        upstream=lambda name: name if mode == "federation" else f"STREAM({name})",
        shot=shots,
        engine=s["pipeline"]["engine"],
        step1=STEP1[s["pipeline"]["engine"]],
        dbt_where=dbt_where,
        dbt_path=lambda path: path.replace(s["_derived"]["catalog"], "{{ target.catalog }}"),
    )


def render_lab_files(env: Environment, ctx: dict, out_dir: Path) -> None:
    s = ctx["s"]

    def lab(tpl: str, out_rel: str, **extra):
        text = env.get_template(f"lab-files/{tpl}").render(**ctx, **extra)
        out = out_dir / out_rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text)

    if s["pipeline"]["engine"] == "dbt":
        lab("dbt/dbt_project.yml.j2", "step1/dbt/dbt_project.yml")
        lab("dbt/schema.yml.j2", "step1/dbt/models/schema.yml")
        for src in s["sources"]:
            lab("dbt/bronze.sql.j2", f"step1/dbt/models/bronze/{src['bronze']}.sql", src=src)
            lab("dbt/silver.sql.j2", f"step1/dbt/models/silver/{src['silver']['table']}.sql", src=src)
        lab("dbt/gold.sql.j2", f"step1/dbt/models/gold/{s['gold']['table']}.sql")
    else:
        for name in ("bronze", "silver", "gold"):
            lab(f"step1/{name}.sql.j2", f"step1/{name}.sql")
    for ds in s["dashboard"]["datasets"].values():
        lab("step2/dataset.sql.j2", f"step2/{ds['file']}", ds=ds)
    for mv in s["metric_views"]:
        lab("step3/mv.yaml.j2", f"step3/{mv['name']}.yaml", mv=mv)


def render(workshop_dir: Path) -> None:
    s = load_spec(workshop_dir / "workshop.yaml")
    shots = Shots(workshop_dir, s["lab"]["inherit_images"], s["lab"]["inherit_exclude"])
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

    engine = s["pipeline"]["engine"]
    for tpl in sorted((TEMPLATES / "docs").rglob("*.md.j2")):
        rel = tpl.relative_to(TEMPLATES / "docs").as_posix()
        if rel in skip:
            continue
        if rel.endswith(".dbt.md.j2"):
            if engine != "dbt":
                continue
            out_name = rel[: -len(".dbt.md.j2")] + ".md"
        else:
            if engine == "dbt" and (TEMPLATES / "docs" / (rel[: -len(".md.j2")] + ".dbt.md.j2")).is_file():
                continue
            out_name = rel[: -len(".j2")]
        out_rel = page_names.get(rel, out_name)
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
    if s["lab"]["inherit_images"] and (ROOT / s["lab"]["inherit_images"] / "images").is_dir():
        shutil.copytree(ROOT / s["lab"]["inherit_images"] / "images", assets_out / "images", dirs_exist_ok=True,
                        ignore=lambda d, names: [n for n in names if any(Path(d, n).as_posix().endswith("/" + x) for x in s["lab"]["inherit_exclude"])])
    if (workshop_dir / "images").is_dir():
        shutil.copytree(workshop_dir / "images", assets_out / "images", dirs_exist_ok=True)
    (assets_out / "files").mkdir(exist_ok=True)
    if s["options"]["volumes"]:
        for d in s["volume"]["docs"]:
            src = workshop_dir / "files" / d["file"]
            if not src.is_file() and s["lab"]["inherit_images"]:
                src = ROOT / s["lab"]["inherit_images"] / "files" / d["file"]
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
