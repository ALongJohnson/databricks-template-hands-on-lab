# Databricks Hands-on Lab Template

A reusable, data-driven version of the [Wanderbricks Hands-on Lab](https://github.com/Jiyu-Kim/databricks-wanderbricks-hands-on-lab).
Every workshop built from it has **the same 7 steps and the same outputs**: a Lakeflow pipeline
(Bronze, Silver, Gold), an AI/BI dashboard, Unity Catalog Metric Views and a Domain, a Genie Agent
improved with Monitoring, Benchmark and Pages, documents in a Volume, and Genie One. What changes
per workshop is the **data**, the **architecture** it comes from, and the **story**.

```
workshops/<name>/workshop.yaml ──┐
templates/ (pages, SQL, nav)  ───┼─► scripts/render.py ─► docs/eng + lab-files/eng ─► Zensical ─► site/
docs/assets/ (CSS, generic UI) ──┘
```

A Claude skill, `.claude/skills/adapt-hands-on-lab`, adapts the template to new data and
architecture: it profiles the data, writes the spec, dry-runs it on a workspace to measure every
number, and builds the site.

## Track 1 on this branch (`genie_agent`)

This branch publishes **Track 1: Create a Genie Agent and serve it as an MCP**
(`workshops/genie-agent-mcp`, set in `.workshop`). It reuses the Wanderbricks data, story, numbers and
screenshots, drops the AI/BI dashboard step, and adds two steps: serving the Genie Agent over the Genie Agent MCP
and the Genie One MCP (coding agent, Python product agent, Unity Gateway governance), and a bring-your-own-data
planning page. The reference workshop still renders exactly as on `main`.

## Repository layout

```
templates/                 # page, lab-file and nav templates (shared by every workshop; Jinja2)
workshops/
  wanderbricks/            # reference example: reproduces the original lab
    workshop.yaml          #   the spec: data, architecture, story, expected results
    images/                #   screenshots that show this workshop's data
    files/                 #   Step 4.5 PDFs
docs/assets/               # CSS, JS, logo, persona avatars, data-free UI screenshots
scripts/
  render.py                # spec + templates -> site sources (also writes SCREENSHOTS_TODO.md)
  validate.py              # checks a spec against the lab contract
  new_workshop.py          # starts workshops/<name>/ from the reference
  dryrun.py                # builds the pipeline + Metric Views on a workspace and measures every number
  make_documents.py        # Step 4.5 PDFs from markdown in the spec
  build.sh                 # validate + render + zensical build
.claude/skills/adapt-hands-on-lab/   # the Claude skill and its references
```

`docs/eng/`, `lab-files/` and `zensical.eng.toml` are generated and git-ignored. Edit
`templates/` or the spec, never the generated files.

## Quick start

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
ZENSICAL=.venv/bin/zensical PYTHON=.venv/bin/python scripts/build.sh          # builds the reference
.venv/bin/zensical serve -f zensical.eng.toml -a localhost:8000
```

## Build a workshop for new data

With Claude Code, open this repo and ask: *"Create a workshop for <fictional company> from
<tables or files> arriving via <architecture>."* The `adapt-hands-on-lab` skill runs the steps
below. By hand:

```bash
.venv/bin/python scripts/new_workshop.py acme-retail          # copy the reference spec
# edit workshops/acme-retail/workshop.yaml (see .claude/skills/adapt-hands-on-lab/references/)
.venv/bin/python scripts/validate.py --workshop workshops/acme-retail
.venv/bin/python scripts/dryrun.py --workshop workshops/acme-retail --profile <cli-profile> --warehouse-id <id>
#   -> copy measured numbers from workshops/acme-retail/measured.yaml into the spec
.venv/bin/pip install -r requirements-tools.txt && .venv/bin/python scripts/make_documents.py --workshop workshops/acme-retail
WORKSHOP=workshops/acme-retail ZENSICAL=.venv/bin/zensical PYTHON=.venv/bin/python scripts/build.sh
```

### What the data must look like

One **dimension** table, a **main fact** (with an amount, a status or type column, and dates) and
a **secondary fact** with many rows per main-fact row, plus some real data-quality issues. The full
contract, and why each piece is needed, is in
[`references/contract.md`](.claude/skills/adapt-hands-on-lab/references/contract.md).

### Architectures supported

| `architecture.mode` | Source | Bronze reads with |
|---|---|---|
| `uc_table` | Unity Catalog tables | `STREAM(catalog.schema.table)` |
| `files` | a Volume or S3 / ADLS / GCS path | Auto Loader `read_files()` |
| `federation` | Redshift, Snowflake, BigQuery, PostgreSQL... via Lakehouse Federation | batch Materialized Views |

`architecture.upstream` draws the customer's own systems on the home-page diagram. Details:
[`references/architecture-modes.md`](.claude/skills/adapt-hands-on-lab/references/architecture-modes.md).

### Screenshots

`docs/assets/images/` holds only screenshots with no example data in them (menus, dialogs).
Screenshots that show data live in each workshop's `images/` folder under the same path. A page
shows a screenshot only if the file exists, so a new workshop renders cleanly with text alone;
`workshops/<name>/SCREENSHOTS_TODO.md` lists what to capture.

## Publishing

Push to `main` and GitHub Actions publishes the workshop named in the one-line `.workshop`
file (default `workshops/wanderbricks`) to GitHub Pages.

The site also hosts one lab **track per branch**. A push to `main`, `genie_agent` or `agent_bricks`
rebuilds every branch and publishes them together:

| Branch | Path | Lab |
|---|---|---|
| `main` | `/` | Reference lab |
| `genie_agent` | `/genie_agent/` | Track 1: Create a Genie Agent and serve it as an MCP |
| `agent_bricks` | `/agent_bricks/` | Track 2: Move your agentic system onto Databricks and apply enterprise governance |

Each branch builds with its own `scripts/build.sh`. To add a track, add the branch to `on.push.branches`
and `TRACKS` in `.github/workflows/deploy-pages.yml`, on every branch. Locally, `WORKSHOP=workshops/<name>`
overrides it. **This repository is public**:
only commit anonymized data descriptions and fictional company names. For a customer-specific
workshop, use a private fork.

## Credits

Content, structure and screenshots of the reference workshop: [Jiyu Kim's Wanderbricks Hands-on Lab](https://github.com/Jiyu-Kim/databricks-wanderbricks-hands-on-lab).
The Korean edition lives in the upstream repository; this template is English-only (add a
language by adding a translated `templates/` set and a second nav config).
