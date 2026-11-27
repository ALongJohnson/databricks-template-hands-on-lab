"""Run the external Wanda agent from the command line.

    uv run wanda "I want to cancel booking 532. How much do I get back?"
"""
import asyncio
import os
import sys

from agents import OpenAIChatCompletionsModel, Runner, set_tracing_disabled
from dotenv import load_dotenv
from openai import AsyncOpenAI

from wanda.agent import build_agent


def enable_mlflow_tracing() -> None:
    """Step 3: three lines send every model call and tool call to MLflow as a trace."""
    import mlflow

    mlflow.set_experiment(experiment_id=os.environ["MLFLOW_EXPERIMENT_ID"])
    mlflow.openai.autolog()  # traces OpenAI Agents SDK runs, model calls and tool calls


async def ask(question: str) -> str:
    client = AsyncOpenAI(base_url=os.environ["MODEL_BASE_URL"], api_key=os.environ["MODEL_API_KEY"])
    model = OpenAIChatCompletionsModel(model=os.environ["MODEL_NAME"], openai_client=client)
    result = await Runner.run(build_agent(model), question)
    return result.final_output


def main() -> None:
    load_dotenv()
    if os.getenv("MLFLOW_EXPERIMENT_ID"):
        enable_mlflow_tracing()  # MLflow replaces the SDK's default trace exporter
    else:
        set_tracing_disabled(True)  # no tracing at all, which is where most teams start
    question = " ".join(sys.argv[1:]) or "What is the status of booking 532?"
    print(asyncio.run(ask(question)))


if __name__ == "__main__":
    main()
