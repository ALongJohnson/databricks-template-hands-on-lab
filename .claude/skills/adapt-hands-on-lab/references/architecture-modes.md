# Mapping the customer's architecture

`architecture.mode` decides how Bronze reads the source and what the Prerequisites page asks for.
Everything after Bronze is identical in every mode.

| The customer's data is... | mode | Bronze becomes | Prerequisite added |
|---|---|---|---|
| already in Unity Catalog tables (or Delta Shared, or a copy you load) | `uc_table` | `STREAMING TABLE ... FROM STREAM(catalog.schema.table)` | none |
| files landing in a Volume or cloud storage (S3, ADLS, GCS): CSV, JSON, Parquet, from SFTP drops, Kinesis/Kafka sinks, exports | `files` | `STREAMING TABLE ... FROM STREAM read_files('<path>', format => ...)` (Auto Loader); `_source` = `_metadata.file_path` | READ VOLUME (Volume path) or READ FILES on the external location (cloud path) |
| in a warehouse or database reachable through Lakehouse Federation (Redshift, Snowflake, BigQuery, PostgreSQL, MySQL, SQL Server, Synapse) | `federation` | `MATERIALIZED VIEW ... FROM foreign_catalog.schema.table`; Silver also becomes Materialized Views (no STREAM) | USE CATALOG and SELECT on the foreign catalog |

## Spec fields per mode

```yaml
architecture:
  mode: files
  source_label: s3://acme-landing/raw          # label on the diagrams
  files: { root: s3://acme-landing/raw/, format: csv, options: { header: true } }
  upstream:                                    # optional: draws the customer's systems on the home page
    - label: Operational systems
      nodes:
        - { name: Orders service, detail: PostgreSQL → nightly CSV }
        - { name: Clickstream, detail: Kinesis → S3 }
sources:
  - { name: customers, role: dimension, path: s3://acme-landing/raw/customers/, rows: 50000, ... }
  # per-source `format` and `options` override architecture.files
```

```yaml
architecture:
  mode: federation
  source_label: redshift_prod.sales
  federation: { system: Amazon Redshift, foreign_catalog: redshift_prod }
sources:
  - { name: customers, role: dimension, ref: redshift_prod.sales.customers, rows: 50000, ... }
```

## Facilitator setup

Whatever must exist before learners arrive goes in `source.facilitator_setup` (markdown, shown on
the Prerequisites page): the Volume or external location, the foreign catalog and connection,
grants to the learner group, and the warehouse. Also set:

- `source.noun` ("sample data", "source files", "Redshift tables")
- `source.intro`, `source.browse_step`, `source.browse_alt` (how a learner sees the data in Catalog Explorer)
- `lab.hero_data_fact` (home page fact, e.g. "Anonymized retail data")

## Streaming sources (Kinesis, Kafka, Event Hubs)

Not a mode yet. Land them to files (most customers already do: Firehose to S3, Kafka Connect
sink) and use `files`. A native `read_kinesis` / `read_kafka` Bronze needs a service credential
per learner and is a template change: propose it before doing it.

## Region notes worth checking in the target workspace

- Genie Agent **Chat** mode can be unavailable in some regions unless cross-geo processing is on.
  The lab already uses **Agent** mode by default, and Step 4.5 requires it.
- Step 4.5 needs Lakebase and the "Analyze Files in Volumes with Genie Agents" preview.
- Step 5 needs the "Genie Ontology snippets" preview.
Set `options.volumes: false` when 4.5 cannot run; say so in `source.facilitator_setup`.
