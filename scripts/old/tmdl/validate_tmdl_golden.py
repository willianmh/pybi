"""CI-safe TMDL golden-file validation script.

Serializes ``report/contoso/ContosoSample.SemanticModel`` (model.bim) with the
current TmdlStrategy and diffs every ``.tmdl`` output file against the committed
golden files in ``tests/golden/tmdl/contoso/``.

Exits with code 0 on success, code 1 if *any* file differs or is missing.
Prints a unified diff for every failing file so CI logs are self-explanatory.

Usage
-----
    # Normal CI check:
    uv run python scripts/tmdl/validate_tmdl_golden.py

    # Verbose – shows identical files too:
    uv run python scripts/tmdl/validate_tmdl_golden.py --verbose

    # Regenerate golden files (run this when an intentional change is made):
    uv run python scripts/tmdl/generate_tmdl_golden.py
"""

from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "src"))

from poupytempo.persistence.strategies.model_bim import ModelBimStrategy  # noqa: E402
from poupytempo.persistence.strategies.tmdl import TmdlStrategy  # noqa: E402
from poupytempo.persistence.transports.local import LocalTransport  # noqa: E402

_SM_PATH = str(_REPO_ROOT / "report" / "contoso" / "ContosoSample.SemanticModel")
_GOLDEN_DIR = _REPO_ROOT / "tests" / "golden" / "tmdl" / "contoso"

# ──────────────────────────────────────────────────────────────────────────────


def _load_golden(rel_path: str) -> str | None:
    """Return golden file text, or None if the file is absent."""
    golden = _GOLDEN_DIR / rel_path
    if not golden.exists():
        return None
    return golden.read_text(encoding="utf-8")


def _unified_diff(golden_text: str, actual_text: str, label: str) -> list[str]:
    return list(
        difflib.unified_diff(
            golden_text.splitlines(keepends=True),
            actual_text.splitlines(keepends=True),
            fromfile=f"golden/{label}",
            tofile=f"actual/{label}",
            n=3,
        )
    )


# ──────────────────────────────────────────────────────────────────────────────


def run(*, verbose: bool = False) -> int:
    """Serialize Contoso model.bim and compare against golden files.

    Returns 0 on success, 1 if any file differs.
    """
    print(f"Loading model.bim: {_SM_PATH}")
    transport = LocalTransport()
    bim = ModelBimStrategy()
    tmdl = TmdlStrategy()

    parts = transport.read_parts(_SM_PATH)
    sm = bim.deserialize(parts)
    tmdl_parts = [p for p in tmdl.serialize(sm) if p.path.endswith(".tmdl")]

    failures: list[str] = []
    golden_missing: list[str] = []
    unexpected_extra: list[str] = []

    # Check every serialized part against its golden file
    golden_paths = {str(p.path) for p in tmdl_parts}
    for part in sorted(tmdl_parts, key=lambda p: p.path):
        actual_text = part.as_text()
        golden_text = _load_golden(part.path)

        if golden_text is None:
            print(f"  MISSING GOLDEN : {part.path}")
            golden_missing.append(part.path)
            continue

        diff = _unified_diff(golden_text, actual_text, part.path)
        if diff:
            print(f"  DIFF           : {part.path}")
            print("".join(diff))
            failures.append(part.path)
        elif verbose:
            print(f"  OK             : {part.path}")

    # Flag golden files that have no corresponding serialized part (deleted files)
    for golden_file in sorted(_GOLDEN_DIR.rglob("*.tmdl")):
        rel = golden_file.relative_to(_GOLDEN_DIR).as_posix()
        if rel not in golden_paths:
            print(f"  EXTRA GOLDEN   : {rel}  (golden exists but serializer no longer produces it)")
            unexpected_extra.append(rel)

    # ── Summary ──────────────────────────────────────────────────────────────
    total = len(tmdl_parts)
    ok = total - len(failures) - len(golden_missing)
    print()
    print(f"Results: {ok}/{total} file(s) identical")

    all_failures = failures + golden_missing + unexpected_extra
    if all_failures:
        print(f"FAILED ({len(all_failures)} issue(s)):")
        for f in all_failures:
            print(f"  - {f}")
        print()
        print("To regenerate golden files after an intentional serializer change, run:")
        print("  uv run python scripts/tmdl/generate_tmdl_golden.py")
        return 1

    print("All golden files match. OK")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--verbose", "-v", action="store_true", help="Print OK files too")
    args = parser.parse_args()
    sys.exit(run(verbose=args.verbose))


if __name__ == "__main__":
    main()
