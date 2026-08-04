from __future__ import annotations

import argparse
import json
from pathlib import Path

from rolecheck.analysis.gate6_posthoc import (
    EXPECTED_HASHES,
    build_counterfactual_records,
    evaluate_records,
    preflight_gate6,
)
from rolecheck.analysis.verifier import verify_analysis


def main() -> None:
    parser = argparse.ArgumentParser(description="CPU-only Gate 6.1A analysis")
    parser.add_argument("mode", choices=("preflight", "build", "evaluate", "verify"))
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--gate3-root", type=Path)
    parser.add_argument("--output-root", type=Path)
    args = parser.parse_args()
    if args.mode in {"preflight", "build"} and args.gate3_root is None:
        parser.error("--gate3-root is required")
    if args.mode in {"build", "evaluate", "verify"} and args.output_root is None:
        parser.error("--output-root is required")
    if args.mode == "preflight":
        result = preflight_gate6(args.source_root, args.gate3_root)
    elif args.mode == "build":
        result = build_counterfactual_records(args.source_root, args.gate3_root, args.output_root)
    elif args.mode == "evaluate":
        result = evaluate_records(args.source_root, args.output_root)
    else:
        result = verify_analysis(args.output_root, expected_source_hash=EXPECTED_HASHES["root"])
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
