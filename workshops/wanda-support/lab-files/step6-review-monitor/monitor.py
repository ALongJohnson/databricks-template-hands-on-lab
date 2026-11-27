"""Step 6: keep judging Wanda in production, and send real conversations to a human reviewer.

    # start judges that score a sample of every new trace
    uv run python monitor.py start --experiment-id <id> --warehouse-id <sql-warehouse-id>
    # send the latest traces to your support lead for review
    uv run python monitor.py review --experiment-id <id> --warehouse-id <id> --reviewer lead@yourstartup.com
"""
import argparse
import os

import mlflow
from dotenv import load_dotenv
from mlflow.genai import create_labeling_session, label_schemas
from mlflow.genai.scorers import Guidelines, Safety, ScorerSamplingConfig, list_scorers
from mlflow.tracing import set_databricks_monitoring_sql_warehouse_id

POLICY = Guidelines(
    name="follows_refund_policy",
    guidelines=[
        "Any refund amount in the response must follow the refund policy: a full refund 14 or more "
        "days before check-in, 50% at 7 to 13 days, and nothing at less than 7 days.",
        "The response must not state refund timelines (for example 'within 5 days'), fees, vouchers "
        "or compensation, because the refund policy does not define any.",
    ],
)


def start(a) -> None:
    set_databricks_monitoring_sql_warehouse_id(sql_warehouse_id=a.warehouse_id, experiment_id=a.experiment_id)
    existing = {s.name for s in list_scorers()}
    for name, judge, rate in (("prod_safety", Safety(), 1.0), ("prod_follows_refund_policy", POLICY, a.sample_rate)):
        if name in existing:
            print(f"{name} already registered")
            continue
        judge.register(name=name).start(sampling_config=ScorerSamplingConfig(sample_rate=rate))
        print(f"Started {name} on {rate:.0%} of new traces")


def review(a) -> None:
    label_schemas.create_label_schema(
        name="follows_refund_policy", type="feedback", title="Does Wanda follow the refund policy?",
        input=label_schemas.InputCategorical(options=["yes", "no"]), enable_comment=True, overwrite=True,
    )
    traces = mlflow.search_traces(locations=[a.experiment_id], max_results=a.max_traces,
                                  order_by=["timestamp_ms DESC"], return_type="list")
    session = create_labeling_session(name="wanda-policy-review", assigned_users=[a.reviewer],
                                      label_schemas=["follows_refund_policy"])
    session.add_traces(traces)
    print(f"Sent {len(traces)} traces for review. Share this link with {a.reviewer}: {session.url}")


def main() -> None:
    load_dotenv()
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("start")
    s.add_argument("--sample-rate", type=float, default=0.5)
    r = sub.add_parser("review")
    r.add_argument("--reviewer", required=True)
    r.add_argument("--max-traces", type=int, default=10)
    for p in (s, r):
        p.add_argument("--experiment-id", required=True)
        p.add_argument("--warehouse-id", required=True, help="SQL warehouse that reads the trace tables")
    a = ap.parse_args()
    os.environ["MLFLOW_TRACING_SQL_WAREHOUSE_ID"] = a.warehouse_id
    mlflow.set_tracking_uri("databricks")
    mlflow.set_experiment(experiment_id=a.experiment_id)
    {"start": start, "review": review}[a.cmd](a)


if __name__ == "__main__":
    main()
