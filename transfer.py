"""Export and import a Repsy profile without including it in git."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import store

SCHEMA_VERSION = 1


def export_profile(destination: Path) -> None:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "config": store.load_config(),
        "log": store.load_log(),
        "state": store.load_state(),
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def import_profile(source: Path) -> None:
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"Unsupported Repsy export: expected schema version {SCHEMA_VERSION}")
    config, log, state = payload.get("config"), payload.get("log"), payload.get("state")
    if not isinstance(config, dict) or not isinstance(log, dict) or not isinstance(state, dict):
        raise ValueError("Repsy export must contain config, log, and state objects")
    if not isinstance(log.get("sets", []), list):
        raise ValueError("Repsy log has an invalid sets list")
    store._atomic_write(store.CONFIG_PATH, config)
    store._atomic_write(store.LOG_PATH, log)
    store._atomic_write(store.STATE_PATH, state)


def main() -> None:
    parser = argparse.ArgumentParser(description="Move a Repsy profile between computers")
    sub = parser.add_subparsers(dest="command", required=True)
    export = sub.add_parser("export", help="write a profile export")
    export.add_argument("destination", type=Path)
    import_ = sub.add_parser("import", help="replace the current profile")
    import_.add_argument("source", type=Path)
    args = parser.parse_args()
    if args.command == "export":
        export_profile(args.destination)
    else:
        import_profile(args.source)


if __name__ == "__main__":
    main()
