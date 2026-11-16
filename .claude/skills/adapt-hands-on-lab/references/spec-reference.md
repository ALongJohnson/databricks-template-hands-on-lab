# workshop.yaml field reference

Every field below appears in `workshops/wanderbricks/workshop.yaml`; read that file next to this
one. Strings are markdown unless noted. `${catalog}` expands to `<your_name>_<naming.catalog>`.
"Measured" means the value must come from `scripts/dryrun.py` (or a `checks:` entry).

## Site and naming

| Field | Drives | Notes |
|---|---|---|
| `lab.company`, `lab.title` | site name, nav, headings | fictional name |
| `lab.site_url`, `lab.repo_url` | site config, feedback link | `repo_url` + `/issues` is the feedback link |
| `lab.hero_data_fact` | home hero fact | e.g. "Anonymized retail data" |
| `lab.overview_image`, `overview_alt`, `scenario_image_alt` | home hero art, scenario page | optional; defaults to the generic `00-introduction/overview-generic.svg` |
| `options.genie_code_pipeline`, `options.volumes` | include Step 1.4 / 4.5 | default true |
| `naming.*` | every asset name | `catalog` doubles as Domain and Governed Tag name; `example_user` is the sample learner name |

## Story (Introduction pages)

| Field | Drives |
|---|---|
| `company.summary` | home overview sentence |
| `company.what_is`, `company.traits[]` | Scenario: "What is X?" |
| `company.problem_intro`, `problem_quote`, `problem_bullets[]`, `scar` | Scenario: the problem. Make the quote the monitoring trap ("same question, different numbers"); make one bullet the Step 4.5 document question |
| `personas.<data_engineer, data_analyst, ai_engineer, business_user>` | `name`, `title`, `home_role`, `quote`, `daily[]`, optional `avatar` (defaults to the four generic avatars) |
| `text.journey_step1` | home Step 1 task line |

## Architecture and sources (Prerequisites, Step 1.1)

See `architecture-modes.md`. Per source:

| Field | Notes |
|---|---|
| `name`, `role` | roles must be `dimension`, `fact`, `fact` in that order |
| `ref` or `path` (+ `format`, `options`) | by mode |
| `rows` | measured source row count |
| `bronze` | optional, defaults to `bronze_<name>` |
| `bronze_comment` | table comment |
| `silver.table` | `silver_dim_*` / `silver_fact_*` by convention |
| `silver.header` | SQL comment above the table ("From N source rows, removed M ... → K rows"), measured |
| `silver.comment` | table comment |
| `silver.constraints[]` | `{name, expr, action: drop | warn | fail}`; put the key NOT NULL rule first (it sets the alignment); include one `warn` rule somewhere |
| `silver.select` | the projection, one column per line |
| `silver.rows` | measured |
| `silver.rules_summary`, `silver.removed_text` | the 1.2 Expectations table |
| `pipeline.overview` | Step 1 intro sentence |
| `pipeline.expectations_note` | optional 1.3 info box (e.g. rows that violate two rules at once) |

## Gold (Step 1.2, 1.3)

`table`, `title` (nav: "Silver & Gold: Cleanse and <title>"), `grain` ("one row per customer"),
`primary_key`, `comment`, `columns[] {name, type, not_null, comment}` (comments: value range, what
NULL means, PII), `sql_note` (SQL comment explaining the fan-out), `sql` (everything after `AS`,
CTEs that pre-aggregate each fact then LEFT JOIN to the dimension), `intro`, `key_columns[]`,
`tip_title` / `tip` (why aggregate first), `rows` (measured), `rows_note`, `total_note`.

## Genie Code pipeline (Step 1.4)

`prompt` (rebuilds Steps 1.1 to 1.3 exactly: list every table, every rule, the gold columns, the
fan-out condition, comments and PK; mirror the reference structure), `tip`, `graph_removed` (the
removed counts in the order the graph shows them, after a run), `vdp_goal`, `vdp_prompt`
(`${catalog}.<genie_code_schema>` tables), `vdp_flow_example`, `vdp_operator_review`, `vdp_operator_alt`.

## Dashboard (Step 2)

| Field | Notes |
|---|---|
| `title`, `overview`, `audience`, `subject` | |
| `datasets.main` | `name`, `file`, `header`, `intro`, `columns_intro`, `columns[] {name, meaning, vals}`, optional `note`, `sql` on `${catalog}.default.<gold>` adding analytic buckets (prefix bucket labels with `1)`, `2)` so axes sort) |
| `datasets.histogram` | entities with a non-null value only (`row_unit`, `rows` measured, `note` explaining the null bucket) |
| `datasets.bubble` | one row per group with enough members (`row_unit`, `rows` measured) |
| `widgets.heatmap` | `x`, `y` (main dataset buckets), `color` + `color_agg`, `title`, `title_short`, `shows`, `intro`, `color_agg_note`, `verify` (measured), `tip` |
| `widgets.histogram` | `x` (histogram dataset), `bin_size`, `bin_note`, `verify` |
| `widgets.stacked_bar` | `x`, `color` (main dataset), `color_note`, `swap_note`, optional `verify` |
| `widgets.bubble` | `x`, `y`, `size`, `color` (bubble dataset), `point_note`, `size_note`, `verify`, `tip` |
| `genie_code` | `prompt` (KPI counters + 4 charts + top-N table, every metric defined), `prompt_tip`, `expected[] {item, widget}` (with measured counter values), `followup_intro`, `followup_prompt`, `refine_example`, `local_metrics` (the metrics only defined in dashboard SQL; Step 3 opens with them) |

## Semantics (Step 3)

`domain.subtitle`, `domain.description`, `domain.assets_noun`.

`metric_views[0]` (main fact) and `metric_views[1]` (secondary fact): `name`, `slug` (page file
name), `title`, `subject`, `kpi_noun`, `kpi_summary`, `yaml` (full Metric View YAML: source on the
Silver fact, join to the Silver dimension, dimensions and measures with `comment`, `synonyms`,
`format`; the counts on the page are derived from it), `queries[]` (`[0]`: totals with measured
`verify`; Metric View 1 needs a `[1]` sliced query with `intro` and `shot_alt`), `note` (optional).
Metric View 1 also needs `why_silver` and `explain {source, joins, synonyms_example, formats}`; its
`note` should flag the measure the monitoring trap will misuse. Metric View 2 needs
`why_separate {title, body}` with the measured fan-out numbers.

## Genie Agent and traps (Step 4)

| Field | Notes |
|---|---|
| `genie_agent.overview`, `team`, `why_metric_views`, `description`, `instructions` (data end date, value formats, currency), `common_question`, `first_answer_verify` (measured), `first_answer_measure` | 4.1 |
| `traps.monitoring` | `term`, `persona_quote`, `question`, `question_short`, `wrong_measure` (existing Metric View 1 measure), `verify_wrong`, `explanation`, `table {key_header, rows[] {key, wrong, right}}`, `feedback` |
| `traps.benchmark` | `term`, `question`, `definition`, `ground_truth_sql` (on the **base** Metric View, using existing dimensions), `value` (measured), `score_reason` (what Benchmark reports, e.g. "Filter Issue"), `explanation` |
| `improve.measures[]` | `name`, `expr`, `comment`, `synonyms[]`, `format_ui` (UI instruction), `format` (YAML, used by the dry run) |
| `improve.fields[]` | `name`, `expr`, `comment` (say exact values and how to filter), `synonyms[]` |
| `improve.clarify` | `measure` (usually the trap's `wrong_measure`), `why`, `append` |
| `improve.verify` | `sql`, `columns[]`, `results[]` (measured) |
| `improve.pages[3]` | `name`, `synonyms[]`, `description`, `body` (`## Definition`, a table if useful, `## Business use`, related asset) |
| `improve.pages_example_question`, `benchmark_after`, `reask_verify`, `before_after[2] {before, after}`, `iteration_tip` | 4.4 |
| `volume` | `label`, `docs_noun`, `docs_noun_long`, `docs[2] {file, content, title, source}`, `description`, `chat_mode_symptom`, `questions[2] {summary, from_docs, from_data, prompt, verify, shot_alt}` |

## Genie One and wrap-up (Step 5, 99)

`genie_one.definition_question {prompt, verify, pages[] (names from improve.pages), shot_alt}`,
`genie_one.second_question {title, prompt, verify, shot_alt}`, `wrapup.audience`.

## Measured checks

`checks[] {id, stage: base | improved, sql}`: any extra number quoted in prose (top-N answers,
the trap's wrong and right values, totals). The dry run writes results to `measured.yaml`.
