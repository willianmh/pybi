"""Smoke automation: regenerate models and run strict PBIR validation.

This script is intended for local checks and CI guardrails.
It fails fast if:
  - model generation fails,
  - PBIR validator fails,
  - validator reports Tier 2 as 0/0 (silent strict-skip regression).

Usage:
  uv run python scripts/pbir/smoke_codegen_validate.py
  uv run python scripts/pbir/smoke_codegen_validate.py --no-clean
  uv run python scripts/pbir/smoke_codegen_validate.py --skip-generate
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GEN_SCRIPT = REPO_ROOT / "scripts" / "generate_models.py"
VALIDATE_SCRIPT = REPO_ROOT / "scripts" / "pbir" / "validate_pbir_datamodel.py"

_TIER2_PATTERN = re.compile(r"Tier 2 pass \(strict model\)\s+(\d+)\s*/\s*(\d+)")
_REPORTS_PATTERN = re.compile(r"Discovered\s+(\d+)\s+report\(s\)")


def _run(cmd: list[str], label: str) -> str:
    print(f"\n=== {label} ===")
    print("$", " ".join(cmd))
    result = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )

    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    if result.stderr:
        print(result.stderr, end="" if result.stderr.endswith("\n") else "\n")

    if result.returncode != 0:
        raise RuntimeError(f"{label} failed with exit code {result.returncode}")

    return result.stdout + "\n" + result.stderr


def _assert_validator_metrics(output: str) -> None:
    reports_match = _REPORTS_PATTERN.search(output)
    if not reports_match:
        raise RuntimeError("Could not parse discovered report count from validator output")

    reports_count = int(reports_match.group(1))
    if reports_count <= 0:
        raise RuntimeError("Validator discovered 0 reports")

    tier2_match = _TIER2_PATTERN.search(output)
    if not tier2_match:
        raise RuntimeError("Could not parse Tier 2 metrics from validator output")

    tier2_pass = int(tier2_match.group(1))
    tier2_total = int(tier2_match.group(2))

    if tier2_total == 0:
        raise RuntimeError("Tier 2 strict validation is 0/0 (silent skip regression)")

    if tier2_pass > tier2_total:
        raise RuntimeError(
            f"Invalid Tier 2 metrics: pass={tier2_pass} total={tier2_total}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run PBIR smoke automation: generate models + strict validator"
    )
    parser.add_argument(
        "--skip-generate",
        action="store_true",
        help="Skip model generation and run validator only",
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Generate without --clean",
    )
    args = parser.parse_args()

    python = sys.executable

    try:
        if not args.skip_generate:
            gen_cmd = [python, str(GEN_SCRIPT)]
            if not args.no_clean:
                gen_cmd.append("--clean")
            _run(gen_cmd, "Generate models")

        validate_output = _run(
            [python, str(VALIDATE_SCRIPT), "--verbose"],
            "Validate PBIR datamodel",
        )
        _assert_validator_metrics(validate_output)

        print("\nSMOKE CHECK PASSED")
        return 0
    except RuntimeError as exc:
        print(f"\nSMOKE CHECK FAILED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
