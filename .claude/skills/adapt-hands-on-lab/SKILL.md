---
name: adapt-hands-on-lab
description: Adapt this hands-on lab template to a new customer's data and architecture. Use when asked to "create a workshop for <customer>", "adapt the hands-on lab", "build a lab from this dataset", "new workshop spec", or to change the data, architecture, story, or personas of a workshop in workshops/. Produces workshops/<name>/workshop.yaml (plus PDFs and screenshots) that renders a site with exactly the same 7-step structure and outputs as the reference lab.
---

# Adapt the hands-on lab to new data and architecture

This repo renders one fixed lab (pipeline, dashboard, semantics, Genie Agent, Genie One) from a
per-workshop spec. **The outputs never change. Only the inputs do**: the data, the
architecture it arrives from, and the story told around it. Your job is to write the spec so the
same lessons land on the new data, and to measure every number on a real workspace.

Read before starting:
- `references/contract.md`: the fixed outputs and the data shape they require. Non-negotiable.
- `references/spec-reference.md`: every spec field, which page it drives, and how to fill it.
- `references/architecture-modes.md`: how to map the customer's architecture to `uc_table`, `files` or `federation`.
- `workshops/wanderbricks/workshop.yaml`: the complete worked example. Match its tone, length and level of detail.

## Inputs to collect (ask for anything missing, one round of questions)

1. **Data**: where the anonymized data lives (UC tables, a Volume or S3 path with file format, or a
   foreign catalog), plus a data dictionary if one exists. Never accept identifiable personal
   data; the site is often public.
2. **Architecture**: a diagram or description of the source systems and how data lands. This sets
   `architecture.mode`, `architecture.upstream` and the prerequisites.
3. **Story**: a fictional company name and one-line business (never the real customer name unless
   the user explicitly asks and the repo is private), the business team that will ask questions,
   and any known metric disputes ("revenue means X to finance, Y to marketing").
4. **Workspace for the dry run**: CLI profile and SQL warehouse ID. Never pick a profile yourself.

## Workflow

1. **Profile the data.** For each candidate table or file set: row count, columns and types, keys,
   null rates, duplicates, status or category columns (with distinct values), date columns and
   their range, and the join cardinality between tables. Use SQL on the user's warehouse
   (`databricks api post /api/2.0/sql/statements ... -p <profile>`), or `read_files()` for files.
2. **Fit the contract** (`references/contract.md`). Pick the dimension, the main fact and the
   secondary fact; confirm the secondary fact has many rows per main-fact row (fan-out lesson).
   Choose the gold grain (one row per dimension entity). Find real dirty rows for the Expectations
   (if the data is perfectly clean, say so and ask whether to inject a few known-bad rows into the
   source; never fake the counts). Choose the two **teaching traps** (step 6 below) before writing
   anything else, because Steps 3 to 5 are built around them.
3. **Scaffold**: `python scripts/new_workshop.py <name>` copies the reference spec into
   `workshops/<name>/`. Rewrite every value. Keep the field structure.
4. **Write the spec top to bottom** following `references/spec-reference.md`. Write SQL for the
   pipeline, datasets, Metric View YAML and ground truth; write the Genie Code prompts so they
   produce the same pipeline and dashboard as the SQL (mirror the reference prompts' structure).
5. **Validate**: `python scripts/validate.py --workshop workshops/<name>` until 0 errors. It fails on
   leftover reference terms (Wanderbricks, jiyu, Summer Escape) and contract violations.
6. **Design the two traps** (the heart of Step 4):
   - *Monitoring trap* (4.2): a business term (e.g. "revenue") that has **no measure** in Metric
     View 1, so Genie picks the closest existing measure (`wrong_measure`) and overstates or
     understates the answer. The fix adds the right measure(s) in 4.4 and clarifies the misleading
     one's comment.
   - *Benchmark trap* (4.3): a business term (e.g. "peak season") that needs a **derived field**
     Genie cannot infer, with a ground-truth SQL on the base Metric View. The fix adds the field(s).
   - Three Pages: usually the two monitoring-trap terms plus the benchmark-trap term.
   Both traps must be plausible to the business team and must actually fail before the fix and
   pass after. Confirm this in the workspace walk-through (step 9).
7. **Dry run**: `python scripts/dryrun.py --workshop workshops/<name> --profile <p> --warehouse-id <id>`.
   It builds the pipeline and Metric Views, writes `measured.yaml`, and prints spec vs measured.
   Copy every measured number into the spec, including prose (verify sentences, tables, Page
   bodies). Add a `checks:` entry for every number quoted in prose that is not already measured.
   Rerun until the report is all OK.
8. **Documents (4.5)**: write two short internal documents as markdown in `volume.docs[].source`
   (one with targets per segment that the data partly meets, one with a policy and a threshold the
   data breaches), then `pip install -r requirements-tools.txt && python scripts/make_documents.py --workshop workshops/<name>`.
   The numbers in the documents must be consistent with the measured data.
9. **Walk the UI steps once** in the target workspace (Genie Agent, Monitoring, Benchmark, Pages,
   Genie One, Volumes). Record what Genie actually answers and update `verify_wrong`,
   `first_answer_verify`, `benchmark_after`, `reask_verify` and the Genie One `verify` text. If a
   trap does not fail, change the trap, not the facts.
10. **Screenshots**: `python scripts/render.py --workshop workshops/<name>` writes
    `workshops/<name>/SCREENSHOTS_TODO.md` listing every data-bearing screenshot to capture. Capture
    them during the walk-through (browser automation is fine), 2880px wide, red box on the click
    target, saved under `workshops/<name>/images/<same path>`. Pages render fine without them.
11. **Build and review**: `WORKSHOP=workshops/<name> scripts/build.sh`, then
    `zensical serve -f zensical.eng.toml`. Check every page; the build log must end with
    `No issues found`.
12. **Publish**: commit on a branch. GitHub Pages publishes the workshop named by the repository
    variable `WORKSHOP`. Remind the user that a public repo exposes everything in the spec.

## Rules

- Do not edit `templates/` to fit one customer. If the contract genuinely cannot express the
  customer's case, propose a template change to the user first, and keep the reference rendering
  identical (`workshops/wanderbricks` must still build).
- Every number on the site is measured, never estimated. Say "about" only where the reference does.
- Keep the reference's writing style: second person, numbered steps, one action per step, short
  admonitions. Avoid em dashes.
- `${catalog}` in any spec string becomes the learner's `<your_name>_<naming.catalog>`.
- Optional steps: set `options.genie_code_pipeline` / `options.volumes` to false only if the
  workspace or region lacks the feature (Volumes needs Lakebase and a preview). The validator and
  pages adapt automatically.
