#!/usr/bin/env python3
"""One-shot agent run (local or GitHub Actions)."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.scheduler import Scheduler  # noqa: E402


def main() -> int:
    load_dotenv(ROOT / ".env")
    load_dotenv(ROOT / "config" / ".env")

    config_path = ROOT / "config" / "config.yaml"
    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    logs_dir = ROOT / "logs"
    logs_dir.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(logs_dir / "agent.log", encoding="utf-8"),
        ],
    )

    # Allow CI / local debug to ignore daytime gate
    if "--force" in sys.argv:
        config.setdefault("pacing", {})["daytime_only"] = False

    # Force demo-only run (ignores other portal toggles)
    if "--demo" in sys.argv:
        config.setdefault("pacing", {})["daytime_only"] = False
        portals = config.setdefault("portals", {})
        for name, pcfg in portals.items():
            pcfg["enabled"] = name == "demo"
        portals.setdefault("demo", {})["enabled"] = True

    scheduler = Scheduler(config, root=ROOT)
    summary = scheduler.run_once()

    history_path = logs_dir / "run_history.jsonl"
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        **summary,
    }
    with open(history_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

    print(json.dumps(summary, indent=2))
    return 0 if "kill_switch" not in summary.get("errors", []) else 2


if __name__ == "__main__":
    raise SystemExit(main())
