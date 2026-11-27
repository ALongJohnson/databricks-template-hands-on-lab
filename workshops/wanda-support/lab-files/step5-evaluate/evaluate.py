"""Step 5: evaluate Wanda with MLflow 3 judges, then pass or fail the release.

    # against the deployed agent
    uv run python evaluate.py --app agent-bricks-wanda-support --experiment-id <id> --warehouse-id <id>
    # against `agentbricks dev` on your laptop, before you deploy
    uv run python evaluate.py --url http://localhost:8000 --experiment-id <id> --warehouse-id <id>

Exits with code 1 if any judge's pass rate is below --min-pass-rate, so you can run it in CI.
"""
import argparse
import os
import sys
import time
import uuid

import mlflow
import requests
from databricks.sdk import WorkspaceClient
from dotenv import load_dotenv
from mlflow.genai.scorers import Correctness, Guidelines, RelevanceToQuery, Safety

from eval_dataset import EVAL_DATA

GUIDELINES = [
    Guidelines(
        name="follows_refund_policy",
        guidelines=[
            "Any refund amount in the response must follow the refund policy: a full refund 14 or more "
            "days before check-in, 50% at 7 to 13 days, and nothing at less than 7 days.",
            "The response must not state refund timelines (for example 'within 5 days'), fees, vouchers "
            "or compensation, because the refund policy does not define any.",
        ],
    ),
    Guidelines(
        name="support_tone",
        guidelines="The response must be polite and in plain language a guest understands. It must not show SQL, table or column names, tool names or error messages.",
    ),
]
SCORERS = [Correctness(), RelevanceToQuery(), Safety(), *GUIDELINES]


def make_predict_fn(url: str, headers: dict):
    def predict_fn(question: str) -> str:
        session = str(uuid.uuid4())
        body = {"id": str(uuid.uuid4()), "session_id": session,
                "input": [{"role": "user", "content": question}]}
        for attempt in range(4):  # one small app instance: retry when it is busy
            r = requests.post(f"{url}/api/invocations", json=body, timeout=300,
                              headers={**headers, "X-Routing-Key": session})
            if r.status_code < 500:
                break
            time.sleep(5 * (attempt + 1))
        r.raise_for_status()
        messages = r.json()["output"]["output"]
        answers = [m["content"] for m in messages
                   if m.get("role") == "assistant" and isinstance(m.get("content"), str) and m["content"]]
        return answers[-1] if answers else ""
    return predict_fn


def main() -> None:
    load_dotenv()
    ap = argparse.ArgumentParser()
    target = ap.add_mutually_exclusive_group(required=True)
    target.add_argument("--app", help="Deployed agent app name, e.g. agent-bricks-wanda-support")
    target.add_argument("--url", help="Agent base URL, e.g. http://localhost:8000")
    ap.add_argument("--experiment-id", required=True)
    ap.add_argument("--warehouse-id", required=True, help="SQL warehouse that reads the Unity Catalog trace tables")
    ap.add_argument("--min-pass-rate", type=float, default=0.8)
    a = ap.parse_args()

    w = WorkspaceClient()
    if a.app:
        url, headers = w.apps.get(a.app).url.rstrip("/"), w.config.authenticate()
    else:
        url, headers = a.url.rstrip("/"), {}

    os.environ["MLFLOW_TRACING_SQL_WAREHOUSE_ID"] = a.warehouse_id
    os.environ.setdefault("MLFLOW_GENAI_EVAL_MAX_WORKERS", "2")  # gentle on a single app instance
    mlflow.set_tracking_uri("databricks")
    mlflow.set_experiment(experiment_id=a.experiment_id)
    results = mlflow.genai.evaluate(data=EVAL_DATA, predict_fn=make_predict_fn(url, headers), scorers=SCORERS)

    failed = []
    print(f"\nEvaluation run: {results.run_id}")
    for name, value in sorted(results.metrics.items()):
        if name.endswith("/mean"):
            verdict = "PASS" if value >= a.min_pass_rate else "FAIL"
            failed += [name] if verdict == "FAIL" else []
            print(f"  {verdict}  {name.removesuffix('/mean'):<24} {value:.0%}")
    if failed:
        print(f"\nRelease blocked: {len(failed)} judge(s) below {a.min_pass_rate:.0%}.")
        sys.exit(1)
    print("\nRelease approved: every judge meets the bar.")


if __name__ == "__main__":
    main()
