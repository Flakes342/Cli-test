from __future__ import annotations

import argparse

from amex_ai_agent.config import ConfigLoader
from amex_ai_agent.startup import StartupManager


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sally")
    subcommands = parser.add_subparsers(dest="command")

    subcommands.add_parser("init", help="Collect runtime defaults and optional auth.")
    subcommands.add_parser("run", help="Initialize runtime and start the Sally CLI.")
    subcommands.add_parser("doctor", help="Validate config and startup prerequisites.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    command = args.command or "run"

    loader = ConfigLoader()
    config = loader.load()
    startup = StartupManager(loader)

    if command == "init":
        startup.initialize(config, prompt_for_auth=True)
        return

    if command == "doctor":
        resolved = startup.initialize(config, prompt_for_auth=False)
        print("Saved runtime configuration:")
        print(f"- default_project_id: {resolved.default_project_id}")
        print(f"- default_dataset_id: {resolved.default_dataset_id}")
        print(f"- default_folder_nm: {resolved.default_folder_nm}")
        print(f"- spark_python: {resolved.spark_python}")
        return

    from amex_ai_agent.agent import run_app

    resolved = startup.initialize(config, prompt_for_auth=True)
    run_app(resolved)
