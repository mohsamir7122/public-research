from __future__ import annotations

import argparse
import json
from pathlib import Path

from .pilot import run_pilot
from .search_strategy import build_queries


def main() -> None:
    parser = argparse.ArgumentParser(prog="medical-research")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build-search", help="Build database-specific search queries")
    build.add_argument("--config", required=True, type=Path)
    build.add_argument("--output", required=True, type=Path)
    pilot = subparsers.add_parser("run-pilot", help="Build queries and deduplicate a frozen metadata pilot")
    pilot.add_argument("--config", required=True, type=Path)
    pilot.add_argument("--records", required=True, type=Path)
    pilot.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    if args.command == "build-search":
        config = json.loads(args.config.read_text(encoding="utf-8"))
        payload = {"project_id": config.get("project_id", ""), "queries": build_queries(config)}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(args.output)
    elif args.command == "run-pilot":
        config = json.loads(args.config.read_text(encoding="utf-8"))
        records = json.loads(args.records.read_text(encoding="utf-8"))
        payload = run_pilot(config, records)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(args.output)


if __name__ == "__main__":
    main()
