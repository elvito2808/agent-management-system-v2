#!/usr/bin/env python3
"""Run a read-only global DEX research report for any token name or symbol."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_system.dex_research.global_service import research_token, render_markdown


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("token", help="Any token name or symbol; not restricted to a fixed list")
    parser.add_argument("--network", help="Optional exact provider network slug filter")
    parser.add_argument("--address", help="Optional token contract/mint/asset identifier filter")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--output", help="Optional report output path; stdout is used by default")
    args = parser.parse_args()
    try:
        report = research_token(args.token, network_filter=args.network, address_filter=args.address)
    except ValueError as exc:
        parser.error(str(exc))
    rendered = json.dumps(report.to_dict(), indent=2, ensure_ascii=False) if args.format == "json" else render_markdown(report)
    if args.output:
        destination = Path(args.output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(rendered + "\n", encoding="utf-8")
        print(f"Report written to {destination}")
    else:
        print(rendered)
    return 0 if report.status == "data_found" else (2 if report.status == "insufficient_data" else 0)


if __name__ == "__main__":
    raise SystemExit(main())
