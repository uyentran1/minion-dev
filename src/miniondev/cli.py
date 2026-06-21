"""
Command-line entrypoint for MinionDev - runs the Planner -> Executor pipeline for a
single prompt against a target repository.
"""
import argparse
import os
import sys
import uuid

from miniondev.agent import ExecutorAgent, PlannerAgent
from miniondev.llm.client import BedrockChatClient
from miniondev.models import WorkItem
from miniondev.orchestrator import Orchestrator


def _print_progress(message: str) -> None:
    print(message)


def run(args: argparse.Namespace) -> int:
    if args.repo != ".":
        os.chdir(args.repo)

    llm_client = BedrockChatClient()

    planner = PlannerAgent(llm_client)
    planner.progress_callback = _print_progress

    executor = ExecutorAgent(llm_client)
    executor.progress_callback = _print_progress

    orchestrator = Orchestrator(planner=planner, executor=executor)

    work_item = WorkItem(
        id=str(uuid.uuid4()),
        title=args.prompt[:80],
        description=args.prompt,
    )

    result = orchestrator.process_work_item(work_item)

    print()
    print("=" * 60)
    print(f"Result: {'SUCCESS' if result.success else 'FAILED'}")
    print(result.message)
    if result.execution_result and result.execution_result.modified_files:
        print(f"Modified files: {', '.join(result.execution_result.modified_files)}")
    if result.errors:
        print(f"Errors: {result.errors}")

    return 0 if result.success else 1


def main() -> None:
    parser = argparse.ArgumentParser(prog="miniondev", description="Autonomous ticket-to-PR pipeline (MVP)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run the Planner -> Executor pipeline for a prompt")
    run_parser.add_argument("--prompt", required=True, help="Description of the work to do")
    run_parser.add_argument("--repo", default=".", help="Path to the target repository (default: current directory)")
    run_parser.set_defaults(func=run)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
