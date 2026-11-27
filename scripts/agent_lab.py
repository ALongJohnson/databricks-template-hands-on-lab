"""Render and validate an agent lab (spec `kind: agent_lab`).

The data-pipeline lab (templates/docs) has a fixed contract built around tables and Metric Views.
An agent lab has a different shape: pages in templates/agent-lab/docs, runnable code in the
workshop's lab-files/ folder, and a small spec of names and measured facts.
"""
from __future__ import annotations

import re
import shutil
import zipfile
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates" / "agent-lab"
DOCS_OUT = ROOT / "docs" / "eng"
LAB_OUT = ROOT / "lab-files" / "eng"
SHARED_ASSETS = ROOT / "docs" / "assets"
SKIP = {".venv", "__pycache__", ".env", "uv.lock", ".DS_Store", "refunds.csv"}
REQUIRED = {"lab": ["company", "title", "site_url", "repo_url", "lab_files_url", "zip"],
            "naming": ["schema", "trace_schema", "experiment", "model_service", "deployment", "app", "model"],
            "facts": ["today", "cases"]}
SECRET = re.compile(r"(dapi[0-9a-f]{20,}|sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16})")


def is_agent_lab(spec_path: Path) -> bool:
    with open(spec_path) as fh:
        return (yaml.safe_load(fh) or {}).get("kind") == "agent_lab"


def _files(lab_dir: Path):
    for p in sorted(lab_dir.rglob("*")):
        if p.is_file() and not any(part in SKIP for part in p.relative_to(lab_dir).parts):
            yield p


def validate(workshop_dir: Path) -> tuple[list[str], list[str]]:
    errors, warns = [], []
    s = yaml.safe_load((workshop_dir / "workshop.yaml").read_text())
    for section, keys in REQUIRED.items():
        for k in keys:
            if k not in (s.get(section) or {}):
                errors.append(f"missing {section}.{k}")
    lab_dir = workshop_dir / "lab-files"
    if not lab_dir.is_dir():
        errors.append(f"missing {lab_dir.relative_to(ROOT)}")
    texts = [workshop_dir / "workshop.yaml", *TEMPLATES.rglob("*.j2")]
    texts += [p for p in _files(lab_dir)] if lab_dir.is_dir() else []
    for p in texts:
        if p.suffix in {".csv", ".png", ".zip"}:
            continue
        t = p.read_text(errors="ignore")
        if "—" in t:
            errors.append(f"em dash in {p.relative_to(ROOT)} (use a colon, comma or parentheses)")
        if SECRET.search(t):
            errors.append(f"possible secret in {p.relative_to(ROOT)}")
    if not (TEMPLATES / "zensical.toml.j2").is_file():
        errors.append("missing templates/agent-lab/zensical.toml.j2")
    return errors, warns


def render(workshop_dir: Path) -> None:
    s = yaml.safe_load((workshop_dir / "workshop.yaml").read_text())
    env = Environment(loader=FileSystemLoader(str(TEMPLATES)), undefined=StrictUndefined,
                      trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True, autoescape=False)
    ctx = {"s": s, "n": s["naming"], "f": s["facts"], "case": {c["booking"]: c for c in s["facts"]["cases"]}}

    for p in (DOCS_OUT, LAB_OUT):
        if p.exists():
            shutil.rmtree(p)
    DOCS_OUT.mkdir(parents=True)
    LAB_OUT.mkdir(parents=True)

    for tpl in sorted((TEMPLATES / "docs").rglob("*.md.j2")):
        rel = tpl.relative_to(TEMPLATES / "docs").as_posix()
        text = env.get_template(f"docs/{rel}").render(**ctx)
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        out = DOCS_OUT / rel[: -len(".j2")]
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text)

    (ROOT / "zensical.eng.toml").write_text(env.get_template("zensical.toml.j2").render(**ctx))

    assets_out = DOCS_OUT / "assets"
    shutil.copytree(SHARED_ASSETS, assets_out)
    if (workshop_dir / "images").is_dir():
        shutil.copytree(workshop_dir / "images", assets_out / "images", dirs_exist_ok=True)
    (assets_out / "files").mkdir(exist_ok=True)

    lab_dir = workshop_dir / "lab-files"
    zpath = assets_out / "files" / s["lab"]["zip"]
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for p in _files(lab_dir):
            rel = p.relative_to(lab_dir)
            z.write(p, Path("wanda-lab-files") / rel)
            dst = LAB_OUT / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst)
    pages = sum(1 for _ in DOCS_OUT.rglob("*.md"))
    print(f"Rendered {workshop_dir.relative_to(ROOT)} (agent lab): {pages} pages, lab files zipped to {zpath.name}")
