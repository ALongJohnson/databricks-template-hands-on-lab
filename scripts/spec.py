"""Load a workshop spec, apply defaults and derived values, and check it against the lab contract.

The contract is what makes every workshop produce the same outputs as the reference lab:
3 sources (1 dimension + 2 facts) -> 3 bronze -> 3 silver (with Expectations) -> 1 gold MV,
3 dashboard datasets + 4 hand-built widgets + 1 Genie Code prompt, 2 Metric Views + 1 Domain,
1 Genie Agent with a Monitoring trap and a Benchmark trap fixed by new measures/fields + Pages,
optional Volume documents, and Genie One questions answered from the Pages.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

PERSONA_KEYS = ("data_engineer", "data_analyst", "ai_engineer", "business_user")
DEFAULT_AVATARS = {
    "data_engineer": "personas/data-engineer.svg",
    "data_analyst": "personas/data-analyst.svg",
    "ai_engineer": "personas/ai-engineer.svg",
    "business_user": "personas/business-user.svg",
}
MODES = ("uc_table", "files", "federation")


def _subst(obj, mapping):
    if isinstance(obj, str):
        for k, v in mapping.items():
            obj = obj.replace("${" + k + "}", v)
        return obj
    if isinstance(obj, list):
        return [_subst(x, mapping) for x in obj]
    if isinstance(obj, dict):
        return {k: _subst(v, mapping) for k, v in obj.items()}
    return obj


def load_raw(path: Path) -> dict:
    with open(path) as fh:
        return yaml.safe_load(fh)


def load_spec(path: Path, catalog_override: str | None = None) -> dict:
    """catalog_override: real catalog name (used by the dry run). Default is the
    learner placeholder `<your_name>_<naming.catalog>`."""
    raw = load_raw(path)
    naming = raw["naming"]
    cat = catalog_override or f"<your_name>_{naming['catalog']}"
    ex_cat = f"{naming['example_user']}_{naming['catalog']}"
    s = _subst(raw, {"catalog": cat, "example_catalog": ex_cat})

    s["lab"].setdefault("overview_image", "00-introduction/overview-generic.svg")
    s["lab"].setdefault("overview_alt", f"{s['lab']['company']}: from raw source data to AI agents on Databricks")
    s["lab"].setdefault("scenario_image_alt", s["lab"]["overview_alt"])
    s.setdefault("options", {})
    s["options"].setdefault("genie_code_pipeline", True)
    s["options"].setdefault("volumes", True)
    arch = s["architecture"]
    arch.setdefault("upstream", [])
    if arch["mode"] == "files":
        arch.setdefault("files", {})
        arch["files"].setdefault("options", {})
    s.setdefault("source", {}).setdefault("facilitator_setup", "")
    for key in PERSONA_KEYS:
        s["personas"][key].setdefault("avatar", DEFAULT_AVATARS[key])
    for src in s["sources"]:
        src.setdefault("bronze", f"bronze_{src['name']}")
    # optional keys (templates test them with {% if %}; StrictUndefined needs them present)
    s.setdefault("pipeline", {}).setdefault("expectations_note", None)
    for k in ("sql_note", "total_note", "rows_note"):
        s["gold"].setdefault(k, "")
    for c in s["gold"]["columns"]:
        c.setdefault("not_null", False)
    for ds in s["dashboard"]["datasets"].values():
        ds.setdefault("note", None)
    for wd in s["dashboard"]["widgets"].values():
        wd.setdefault("tip", None)
        wd.setdefault("verify", "")
    s["improve"].setdefault("clarify", None)
    for m in s["improve"]["measures"]:
        m.setdefault("format_ui", "")

    warn_rules = []
    for src in s["sources"]:
        exprs = [len(f"({c['expr']})") for c in src["silver"]["constraints"]
                 if c.get("action", "drop") != "warn" and len(f"({c['expr']})") <= 26]
        src["silver"]["_wexpr"] = max(exprs, default=0)
        for c in src["silver"]["constraints"]:
            c.setdefault("action", "drop")
            if c["action"] == "warn":
                warn_rules.append({"rule": c["name"], "table": src["silver"]["table"]})
    gc = s.get("genie_code_pipeline", {})
    removed = gc.get("graph_removed") or ", ".join(
        f"{src['rows'] - src['silver']['rows']:,}" for src in s["sources"])

    for mv in s["metric_views"]:
        doc = yaml.safe_load(mv["yaml"])
        mv["_doc"] = doc
        mv["n_measures"] = len(doc.get("measures", []))
        mv["n_fields"] = len(doc.get("dimensions", []))
        mv["measure_names"] = [m["name"] for m in doc.get("measures", [])]
        mv["dimension_names"] = [d["name"] for d in doc.get("dimensions", [])]
        mv["source_table"] = doc["source"].split(".")[-1]
        mv["joins"] = [{"name": j["name"], "table": j["source"].split(".")[-1]} for j in doc.get("joins", [])]
        mv["catalog_refs"] = mv["yaml"].count(cat)
        mv.setdefault("note", None)

    s["_derived"] = {
        "catalog": cat,
        "example_catalog": ex_cat,
        "warn_rules": warn_rules,
        "silver_removed_desc": removed,
    }
    return s


# ---------------------------------------------------------------- contract checks
def validate(path: Path, forbid: list[str] | None = None) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warns: list[str] = []

    def need(cond, msg):
        if not cond:
            errors.append(msg)

    try:
        s = load_spec(path)
    except Exception as exc:  # noqa: BLE001
        return [f"spec failed to load: {exc!r}"], []

    need(s["architecture"]["mode"] in MODES, f"architecture.mode must be one of {MODES}")
    need(len(s["sources"]) == 3, "sources: exactly 3 (1 dimension + 2 facts)")
    roles = [src.get("role") for src in s["sources"]]
    need(roles == ["dimension", "fact", "fact"], "sources[].role must be [dimension, fact, fact] in that order")
    mode = s["architecture"]["mode"]
    for i, src in enumerate(s["sources"]):
        if mode == "files":
            need("path" in src, f"sources[{i}].path required in files mode")
        else:
            need("ref" in src, f"sources[{i}].ref (catalog.schema.table) required in {mode} mode")
        need(isinstance(src.get("rows"), int), f"sources[{i}].rows must be the measured row count (int)")
        sv = src.get("silver", {})
        need(isinstance(sv.get("rows"), int), f"sources[{i}].silver.rows must be an int")
        need(len(sv.get("constraints", [])) >= 1, f"sources[{i}].silver.constraints: at least 1 Expectation")
        if isinstance(src.get("rows"), int) and isinstance(sv.get("rows"), int):
            need(sv["rows"] <= src["rows"], f"sources[{i}]: silver.rows > rows")
    if not any(src["rows"] > src["silver"]["rows"] for src in s["sources"]):
        warns.append("no Expectation drops any row: the 1.3 data-quality lesson will show 0 removed everywhere")
    if not s["_derived"]["warn_rules"]:
        warns.append("no warn-only Expectation (action: warn): the 1.2 'ON VIOLATION options' note loses its example")

    g = s["gold"]
    need(any(c.get("not_null") for c in g["columns"]), "gold.columns: the primary key column needs not_null: true")
    need(g["primary_key"] in [c["name"] for c in g["columns"]], "gold.primary_key must be one of gold.columns")
    need(isinstance(g.get("rows"), int), "gold.rows must be an int")

    ds = s["dashboard"]["datasets"]
    need(set(ds) == {"main", "histogram", "bubble"}, "dashboard.datasets must have keys main, histogram, bubble")
    need(set(s["dashboard"]["widgets"]) == {"heatmap", "histogram", "stacked_bar", "bubble"},
         "dashboard.widgets must have keys heatmap, histogram, stacked_bar, bubble")

    mvs = s["metric_views"]
    need(len(mvs) == 2, "metric_views: exactly 2 (one per fact table)")
    if len(mvs) == 2:
        facts = [src["silver"]["table"] for src in s["sources"][1:]]
        need([mv["source_table"] for mv in mvs] == facts,
             f"metric_views[].yaml source must be the silver fact tables in order {facts}")
        need(len(mvs[0]["queries"]) >= 2, "metric_views[0].queries: 2 queries (total, then sliced)")
        need(len(mvs[1]["queries"]) >= 1, "metric_views[1].queries: 1 query")

    im = s["improve"]
    need(len(im["measures"]) >= 1, "improve.measures: at least 1 (fixes the Monitoring trap)")
    need(len(im["fields"]) >= 1, "improve.fields: at least 1 (fixes the Benchmark trap)")
    need(len(im["pages"]) == 3, "improve.pages: exactly 3 Pages")
    if len(mvs) == 2:
        clash = set(m["name"] for m in im["measures"]) & set(mvs[0]["measure_names"])
        need(not clash, f"improve.measures already exist in {mvs[0]['name']}: {clash}")
        if im.get("clarify"):
            need(im["clarify"]["measure"] in mvs[0]["measure_names"],
                 "improve.clarify.measure must be an existing measure of metric_views[0]")
    t1, t2 = s["traps"]["monitoring"], s["traps"]["benchmark"]
    if len(mvs) == 2:
        need(t1["wrong_measure"] in mvs[0]["measure_names"],
             "traps.monitoring.wrong_measure must be an existing measure of metric_views[0] (what Genie picks)")
    need(str(t2.get("value", "")) != "", "traps.benchmark.value: the ground-truth result")
    gq = s["genie_one"]["definition_question"]["pages"]
    need(all(p in [x["name"] for x in im["pages"]] for p in gq),
         "genie_one.definition_question.pages must be names from improve.pages")
    if s["options"]["volumes"]:
        need(len(s["volume"]["docs"]) == 2, "volume.docs: exactly 2 documents")
        need(len(s["volume"]["questions"]) == 2, "volume.questions: exactly 2 questions")
        for d in s["volume"]["docs"]:
            if not (path.parent / "files" / d["file"]).is_file():
                warns.append(f"volume document not built yet: files/{d['file']} (run scripts/make_documents.py)")

    if forbid:
        text = path.read_text().lower()
        for term in forbid:
            if term.lower() in text:
                errors.append(f"leftover term from the example workshop: '{term}'")
    for key in PERSONA_KEYS:
        need(key in s["personas"], f"personas.{key} missing")
    leftover = re.findall(r"\bTODO\b", path.read_text())
    if leftover:
        errors.append(f"{len(leftover)} TODO marker(s) left in the spec")
    return errors, warns
