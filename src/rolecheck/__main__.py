"""Repository smoke command: validate config and report its stable hash."""

from __future__ import annotations

import argparse

from rolecheck.config import load_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a RoleCheck YAML configuration")
    parser.add_argument("config", help="Path to YAML configuration")
    args = parser.parse_args()
    config = load_config(args.config)
    print(f"valid config: {config.run.experiment_id}")
    print(f"config hash: {config.stable_hash()}")


if __name__ == "__main__":
    main()
