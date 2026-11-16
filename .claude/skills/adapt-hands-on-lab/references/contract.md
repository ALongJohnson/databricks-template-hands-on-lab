# The lab contract

Every workshop built from this template produces the same assets, in the same order, with the
same lessons. `scripts/validate.py` enforces the structural parts; the rest is on you.

## Fixed outputs

| Step | Persona role | Output (always) | Lesson it must still teach |
|---|---|---|---|
| 0 Prereqs | everyone | permissions checked, previews checked, `<your_name>_<catalog>` catalog, source row counts verified | the source data is real and countable |
| 1.1 Bronze | data engineer | 3 Bronze datasets, source kept as-is + `_ingested_at`, `_source` | raw is preserved for reprocessing |
| 1.2 Silver | data engineer | 3 Silver tables with Expectations: DROP ROW rules plus one warn-only rule | quality rules are declarative and measured |
| 1.2 Gold | data engineer | 1 Materialized View, one row per dimension entity, typed columns with comments, PRIMARY KEY, pre-aggregated facts | fan-out is avoided by aggregating before joining |
| 1.3 Run | data engineer | pipeline graph, rows removed per table, gold row count | Expectations results are visible |
| 1.4 (opt.) | data engineer | the same pipeline from one Genie Code prompt; Visual Data Prep flow | AI builds the same thing when the prompt is precise |
| 2.1 to 2.2 | analyst | dashboard, 3 datasets (main + histogram + bubble), 4 hand-built widgets: heatmap, histogram, stacked horizontal bar, bubble | widgets are configured from datasets |
| 2.3 | analyst | the rest of the dashboard from one Genie Code prompt (KPI counters, charts, table) + 1 follow-up fix; published | definitions in the prompt make AI output consistent |
| 3.1 to 3.2 | analyst | 2 Metric Views on the **Silver facts** (one per fact), joined to the Silver dimension | KPIs are defined once at the finest grain; one Metric View per fact avoids fan-out |
| 3.3 | analyst | Domain + Governed Tag, both Metric Views tagged | assets are discoverable by business area |
| 4.1 | AI engineer | Genie Agent on the 2 Metric Views, instructions, one common question | Genie uses governed measures |
| 4.2 | business user, AI engineer | wrong answer to the **monitoring trap**, thumbs-down + comment, seen in Monitor | real users reveal undefined terms |
| 4.3 | AI engineer | 1 benchmark with ground-truth SQL, scores 0% | evaluation is objective |
| 4.4 | AI engineer | new measure(s) + field(s) on Metric View 1, one clarified comment, 3 Pages; benchmark 100%, trap question now right | fix the semantics, then re-measure |
| 4.5 (opt.) | AI engineer | Volume with 2 PDFs connected to the agent; 2 Agent-mode questions mixing documents and data | structured + unstructured answers |
| 5 | business user | 2 Genie One questions answered with Pages cited | Pages standardize terms across the org |
| 99 | everyone | ordered cleanup | |

## Data shape the contract needs

1. **One dimension** table (people, accounts, devices, stores...). Its key is the gold primary key.
2. **A main fact** with: a foreign key to the dimension, an amount (or other summable value),
   a **status or type column** whose values make one business term ambiguous (monitoring trap),
   and **at least two date columns or a date plus a category** so a business period or segment can
   be defined (benchmark trap). Metric View 1, both traps and Step 4.4 live here.
3. **A secondary fact** with many rows per main-fact row or per dimension row (reviews per booking,
   events per session, line items per order). Metric View 2 lives here and proves the fan-out
   reason for two Metric Views.
4. **Real data quality issues** in at least one table (nulls in a required column, impossible
   values, soft-deleted rows). Counts must be measured. One rule should be warn-only.
5. **A grouping with enough members** for the bubble chart (e.g. countries with 500+ customers)
   and a skewed value for the histogram (most entities have none or little; a separate
   "spending" dataset removes the empty ones).
6. Enough volume that numbers look real (thousands to millions of rows), small enough that a
   serverless pipeline finishes in a few minutes.

If the customer's data lacks a piece, fill the gap **in the data** (a derived column in Silver,
an extra source table they can supply) rather than in the template.

## Counts that are fixed (validator errors if not)

3 sources (dimension, fact, fact) · 1 gold · 3 dashboard datasets (main, histogram, bubble) ·
4 widgets (heatmap, histogram, stacked_bar, bubble) · 2 Metric Views on the two Silver facts in
order · Metric View 1 gets at least 1 new measure and 1 new field · 3 Pages · monitoring
`wrong_measure` is an existing Metric View 1 measure · 2 Volume documents and 2 questions when
`options.volumes` is true.
