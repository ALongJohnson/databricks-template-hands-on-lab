#!/usr/bin/env python3
"""Dry-run a workshop on a real workspace and measure every number the guide quotes.

    python scripts/dryrun.py --workshop workshops/<name> --profile <cli-profile> \
        --warehouse-id <sql-warehouse-id> [--catalog hol_dryrun_<name>] [--keep]

What it does (Databricks CLI, serverless pipeline, SQL warehouse):
  1. creates the catalog if missing (drops it at the end only if this run created it)
  2. counts the source data (Prerequisites Task 4)
  3. uploads the rendered bronze/silver/gold SQL and runs them as a Lakeflow pipeline
  4. counts bronze, silver and gold tables (Steps 1.3 and 1.4)
  5. counts the three dashboard datasets (Steps 2.1 and 2.2)
  6. creates both Metric Views and runs their queries (Steps 3.1 and 3.2)
  7. runs the benchmark ground-truth SQL on the base Metric View (Step 4.3)
  8. applies the Step 4.4 measures/fields/clarification and runs the verify query
  9. runs any extra `checks:` from the spec (stage: base | improved)
Writes workshops/<name>/measured.yaml and prints a spec-vs-measured report. It does not
exercise UI-only features (dashboard widgets, Genie Agent answers, Pages, Genie One):
validate those by walking the guide once in the target workspace.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from render import build_context, build_env, render_lab_files, source_count_sql  # noqa: E402
from spec import load_spec  # noqa: E402


class Cli:
    def __init__(self, profile: str, warehouse: str):
        self.profile, self.warehouse = profile, warehouse

    def run(self, *args: str, body: dict | None = None) -> dict:
        cmd = ["databricks", *args, "-p", self.profile, "-o", "json"]
        if body is not None:
            cmd += ["--json", json.dumps(body)]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"{' '.join(args[:3])} failed: {res.stderr.strip() or res.stdout.strip()}")
        out = res.stdout.strip()
        return json.loads(out) if out else {}

    def sql(self, statement: str) -> tuple[list[str], list[list]]:
        r = self.run("api", "post", "/api/2.0/sql/statements", body={
            "warehouse_id": self.warehouse, "statement": statement, "wait_timeout": "50s",
            "on_wait_timeout": "CONTINUE", "format": "JSON_ARRAY", "disposition": "INLINE"})
        while r["status"]["state"] in ("PENDING", "RUNNING"):
            time.sleep(3)
            r = self.run("api", "get", f"/api/2.0/sql/statements/{r['statement_id']}")
        if r["status"]["state"] != "SUCCEEDED":
            raise RuntimeError(f"SQL failed: {r['status'].get('error', {}).get('message')}\n{statement[:400]}")
        cols = [c["name"] for c in r.get("manifest", {}).get("schema", {}).get("columns", [])]
        return cols, r.get("result", {}).get("data_array", []) or []

    def scalar(self, statement: str):
        _, rows = self.sql(statement)
        return rows[0][0] if rows else None


def as_num(v):
    try:
        f = float(v)
        return int(f) if f.is_integer() else round(f, 6)
    except (TypeError, ValueError):
        return v


def improved_yaml(mv: dict, im: dict) -> str:
    doc = copy.deepcopy(mv["_doc"])
    for m in im["measures"]:
        entry = {k: m[k] for k in ("name", "expr", "comment") if k in m}
        entry["display_name"] = m.get("display_name", m["name"])
        entry["synonyms"] = m.get("synonyms", [])
        if m.get("format"):
            entry["format"] = m["format"]
        doc["measures"].append(entry)
    for f in im["fields"]:
        entry = {k: f[k] for k in ("name", "expr", "comment") if k in f}
        entry["display_name"] = f.get("display_name", f["name"])
        entry["synonyms"] = f.get("synonyms", [])
        doc["dimensions"].append(entry)
    if im.get("clarify"):
        for m in doc["measures"]:
            if m["name"] == im["clarify"]["measure"]:
                m["comment"] = f"{m.get('comment', '')} {im['clarify']['append']}".strip()
    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workshop", default=os.environ.get("WORKSHOP", "workshops/wanderbricks"))
    ap.add_argument("--profile", required=True, help="Databricks CLI profile (never defaulted)")
    ap.add_argument("--warehouse-id", required=True)
    ap.add_argument("--catalog", help="catalog to build in (default hol_dryrun_<workshop>)")
    ap.add_argument("--keep", action="store_true", help="keep pipeline, workspace files and catalog")
    args = ap.parse_args()

    wdir = (ROOT / args.workshop).resolve()
    cat = args.catalog or "hol_dryrun_" + wdir.name.replace("-", "_")
    s = load_spec(wdir / "workshop.yaml", catalog_override=cat)
    if s["pipeline"]["engine"] != "sdp":
        raise SystemExit("dryrun.py builds Step 1 as a Lakeflow Spark Declarative Pipeline. For pipeline.engine: dbt, "
                         "run the rendered dbt project (lab-files/eng/step1/dbt) as a Lakeflow Job dbt task first, "
                         "then measure with the Step 1.3 queries. dbt support in the dry run is not built yet.")
    cli = Cli(args.profile, args.warehouse_id)
    m: dict = {"catalog": cat, "sources": {}, "bronze": {}, "silver": {}, "datasets": {},
               "metric_views": {}, "checks": {}}
    created_catalog = False
    pipeline_id = None
    me = cli.run("current-user", "me")["userName"]
    ws_dir = f"/Workspace/Users/{me}/hol-dryrun/{wdir.name}"

    try:
        existing = {r[0] for r in cli.sql("SHOW CATALOGS")[1]}
        if cat not in existing:
            cli.sql(f"CREATE CATALOG {cat}")
            created_catalog = True
        print(f"[1/9] catalog {cat} ({'created' if created_catalog else 'existing'})")

        _, rows = cli.sql(source_count_sql(s))
        m["sources"] = {r[0]: as_num(r[1]) for r in rows}
        print(f"[2/9] source rows {m['sources']}")

        with tempfile.TemporaryDirectory() as tmp:
            env = build_env()
            ctx = build_context(s, lambda *a: "")
            render_lab_files(env, ctx, Path(tmp))
            cli.run("workspace", "mkdirs", ws_dir)
            libs = []
            for name in ("bronze", "silver", "gold"):
                target = f"{ws_dir}/{name}.sql"
                subprocess.run(["databricks", "workspace", "import", target, "--file",
                                str(Path(tmp) / "step1" / f"{name}.sql"), "--format", "RAW",
                                "--overwrite", "-p", args.profile], check=True, capture_output=True)
                libs.append({"file": {"path": target}})
            ds_sql = {k: (Path(tmp) / "step2" / v["file"]).read_text() for k, v in s["dashboard"]["datasets"].items()}
        pipeline_id = cli.run("pipelines", "create", body={
            "name": f"hol-dryrun-{wdir.name}", "catalog": cat, "schema": "default", "serverless": True,
            "development": True, "libraries": libs})["pipeline_id"]
        upd = cli.run("api", "post", f"/api/2.0/pipelines/{pipeline_id}/updates", body={"full_refresh": True})
        print(f"[3/9] pipeline {pipeline_id} update {upd['update_id']} running...")
        while True:
            st = cli.run("api", "get", f"/api/2.0/pipelines/{pipeline_id}/updates/{upd['update_id']}")["update"]["state"]
            if st in ("COMPLETED", "FAILED", "CANCELED"):
                break
            time.sleep(15)
        if st != "COMPLETED":
            ev = cli.run("api", "get", f"/api/2.0/pipelines/{pipeline_id}/events?max_results=30")
            msgs = [e.get("message", "") for e in ev.get("events", []) if e.get("level") == "ERROR"]
            raise RuntimeError(f"pipeline {st}:\n" + "\n".join(msgs[:5]))

        for src in s["sources"]:
            m["bronze"][src["bronze"]] = as_num(cli.scalar(f"SELECT count(*) FROM {cat}.default.{src['bronze']}"))
            t = src["silver"]["table"]
            m["silver"][t] = as_num(cli.scalar(f"SELECT count(*) FROM {cat}.default.{t}"))
        m["gold"] = as_num(cli.scalar(f"SELECT count(*) FROM {cat}.default.{s['gold']['table']}"))
        print(f"[4/9] bronze {m['bronze']} silver {m['silver']} gold {m['gold']}")

        for k, sql in ds_sql.items():
            body = "\n".join(line for line in sql.splitlines() if not line.startswith("--")).strip().rstrip(";")
            m["datasets"][k] = as_num(cli.scalar(f"SELECT count(*) FROM ({body})"))
        print(f"[5/9] dataset rows {m['datasets']}")

        for mv in s["metric_views"]:
            cli.sql(f"CREATE OR REPLACE VIEW {cat}.default.{mv['name']} WITH METRICS LANGUAGE YAML AS $$\n{mv['yaml']}\n$$")
            results = []
            for q in mv["queries"]:
                cols, rows = cli.sql(q["sql"].rstrip().rstrip(";"))
                results.append({"columns": cols, "rows": [[as_num(v) for v in r] for r in rows[:20]]})
            m["metric_views"][mv["name"]] = results
        print("[6/9] metric views created and queried")

        t2 = s["traps"]["benchmark"]
        m["benchmark_value"] = as_num(cli.scalar(t2["ground_truth_sql"].rstrip().rstrip(";")))
        print(f"[7/9] benchmark ground truth = {m['benchmark_value']}")

        def run_checks(stage):
            for c in s.get("checks", []):
                if c.get("stage", "base") == stage:
                    cols, rows = cli.sql(c["sql"].rstrip().rstrip(";"))
                    m["checks"][c["id"]] = {"columns": cols, "rows": [[as_num(v) for v in r] for r in rows[:20]]}

        run_checks("base")
        mv0 = s["metric_views"][0]
        cli.sql(f"CREATE OR REPLACE VIEW {cat}.default.{mv0['name']} WITH METRICS LANGUAGE YAML AS $$\n"
                f"{improved_yaml(mv0, s['improve'])}\n$$")
        cols, rows = cli.sql(s["improve"]["verify"]["sql"].rstrip().rstrip(";"))
        m["improve_verify"] = {"columns": cols, "rows": [[as_num(v) for v in r] for r in rows]}
        print(f"[8/9] improved metric view verify = {m['improve_verify']['rows']}")
        run_checks("improved")
        print(f"[9/9] {len(m['checks'])} extra checks")
    finally:
        if not args.keep:
            if pipeline_id:
                subprocess.run(["databricks", "pipelines", "delete", pipeline_id, "-p", args.profile], capture_output=True)
            subprocess.run(["databricks", "workspace", "delete", ws_dir, "--recursive", "-p", args.profile], capture_output=True)
            if created_catalog:
                try:
                    cli.sql(f"DROP CATALOG {cat} CASCADE")
                except RuntimeError as exc:
                    print(f"cleanup: {exc}")

    out = wdir / "measured.yaml"
    out.write_text("# GENERATED by scripts/dryrun.py. Copy these numbers into workshop.yaml.\n"
                   + yaml.safe_dump(m, sort_keys=False, allow_unicode=True))

    # spec vs measured
    report = []
    for src in s["sources"]:
        report.append((f"sources.{src['name']}.rows", src["rows"], m["sources"].get(src["name"])))
        report.append((f"sources.{src['name']}.silver.rows", src["silver"]["rows"], m["silver"].get(src["silver"]["table"])))
    report.append(("gold.rows", s["gold"]["rows"], m["gold"]))
    for k in ("histogram", "bubble"):
        report.append((f"dashboard.datasets.{k}.rows", s["dashboard"]["datasets"][k].get("rows"), m["datasets"].get(k)))
    report.append(("traps.benchmark.value", as_num(t2["value"]), m["benchmark_value"]))
    bad = [r for r in report if r[1] != r[2]]
    print("\nspec vs measured")
    for key, want, got in report:
        print(f"  {'OK ' if want == got else 'FIX'} {key}: spec={want} measured={got}")
    print(f"\nWrote {out.relative_to(ROOT)}. Also update the prose numbers (verify sentences, tables) from it.")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
