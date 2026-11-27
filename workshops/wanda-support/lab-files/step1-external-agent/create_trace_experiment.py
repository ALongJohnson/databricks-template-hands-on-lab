"""Step 3: create an MLflow experiment whose traces are stored in Unity Catalog tables.

    uv run python create_trace_experiment.py --catalog <catalog> --schema <schema> \
        --warehouse-id <sql-warehouse-id> --experiment /Users/<you>/wanda-support-traces

The schema must already exist. Prints the experiment ID to put in .env as MLFLOW_EXPERIMENT_ID.
"""
import argparse
import os

import mlflow
from dotenv import load_dotenv
from mlflow.entities.trace_location import UnityCatalog


def main() -> None:
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--schema", required=True)
    ap.add_argument("--warehouse-id", required=True)
    ap.add_argument("--experiment", required=True, help="Workspace path, e.g. /Users/you@example.com/wanda-support-traces")
    ap.add_argument("--table-prefix", default="wanda")
    a = ap.parse_args()

    os.environ["MLFLOW_TRACING_SQL_WAREHOUSE_ID"] = a.warehouse_id
    mlflow.set_tracking_uri("databricks")
    exp = mlflow.set_experiment(
        experiment_name=a.experiment,
        trace_location=UnityCatalog(catalog_name=a.catalog, schema_name=a.schema, table_prefix=a.table_prefix),
    )
    print(f"MLFLOW_EXPERIMENT_ID={exp.experiment_id}")
    print(f"Spans table: {exp.trace_location.full_otel_spans_table_name}")


if __name__ == "__main__":
    main()
