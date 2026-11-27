# Wanda lab files

Code for the hands-on lab "Track 2: Move Your Agent onto Databricks". Each folder matches a step.

| Folder | Step | What it is |
|---|---|---|
| `step1-external-agent/` | 1 to 3 | Wanda as it runs today: an OpenAI Agents SDK app on a CSV snapshot, calling a model provider directly. Steps 2 and 3 change only `.env`. |
| `step2-unity-gateway/` | 2 | `model_service.json`: a Unity Gateway model service with rate limits and an inference table. |
| `step4-agent-bricks/` | 4 | `uc_functions.sql` (governed tools), plus the two files you copy into an `agentbricks init` project. |
| `step5-evaluate/` | 5 | `evaluate.py`: MLflow 3 judges and a release gate. |
| `step6-review-monitor/` | 6 | `monitor.py`: production judges and a review session for a human expert. |
| `step7-train-serve/` | 7 | A Databricks notebook that trains, registers and serves a cancellation-risk model. |

Each Python folder is a `uv` project with pinned dependencies: `cd <folder> && uv run ...`.
Copy `.env.example` to `.env` where one exists, and never commit `.env`.

The CSV snapshot in `step1-external-agent/data/` is a small extract of the `samples.wanderbricks`
sample dataset that ships with every Databricks workspace. Wanderbricks is a fictional company.
