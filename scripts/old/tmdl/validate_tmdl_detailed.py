"""
Enhanced TMDL validation script with detailed file comparison.

This script performs a comprehensive validation of TMDL reading and writing:
1. Reads TMDL models from samples/tmdl/ directory
2. Writes them to a temporary output directory
3. Re-reads the written files
4. Performs file-by-file text comparison
5. Reports any differences with detailed diffs

Usage:
    uv run python scripts/validate_tmdl_detailed.py
    uv run python scripts/validate_tmdl_detailed.py --verbose
    uv run python scripts/validate_tmdl_detailed.py --model division-sm
    uv run python scripts/validate_tmdl_detailed.py --keep-output  # Keep temp files for inspection
"""

import os
import sys
import shutil
import logging
import traceback
import difflib
import tempfile
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any

from poupytempo import SemanticModel
from poupytempo.utils.enums import FabricFormat

# Setup logging
logging.basicConfig(level=logging.WARNING, format="%(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class FileComparison:
    """Comparison result for a single file."""

    relative_path: str
    status: str  # "identical", "different", "missing", "extra"
    diff_lines: int = 0
    sample_diff: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class ModelValidation:
    """Complete validation result for a model."""

    name: str
    original_path: str
    output_path: str | None = None

    # Load status
    load_success: bool = False
    load_error: str | None = None

    # Write status
    write_success: bool = False
    write_error: str | None = None

    # Reload status
    reload_success: bool = False
    reload_error: str | None = None

    # Statistics
    tables: int = 0
    columns: int = 0
    measures: int = 0
    relationships: int = 0
    expressions: int = 0

    # File comparison
    files_compared: int = 0
    files_identical: int = 0
    files_different: int = 0
    files_missing: int = 0
    files_extra: int = 0

    file_comparisons: list[FileComparison] = field(default_factory=list)

    # Warnings
    warnings: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """Overall success: all stages passed and all files identical."""
        return (
            self.load_success
            and self.write_success
            and self.reload_success
            and self.files_different == 0
            and self.files_missing == 0
            and self.files_extra == 0
        )


def print_header(title: str) -> None:
    """Print a section header."""
    width = 80
    print("\n" + "=" * width)
    print(f" {title}")
    print("=" * width)


def compare_files(original_file: Path, written_file: Path) -> FileComparison:
    """Compare two TMDL files and return detailed comparison."""
    try:
        with open(original_file, "r", encoding="utf-8") as f:
            original_lines = f.readlines()

        with open(written_file, "r", encoding="utf-8") as f:
            written_lines = f.readlines()

        if original_lines == written_lines:
            return FileComparison(relative_path=original_file.name, status="identical")

        # Generate unified diff
        diff = list(
            difflib.unified_diff(
                original_lines,
                written_lines,
                fromfile=f"original/{original_file.name}",
                tofile=f"written/{written_file.name}",
                lineterm="",
            )
        )

        # Take first 20 lines of diff as sample
        sample_diff = [line.rstrip() for line in diff[:20]]

        return FileComparison(
            relative_path=original_file.name,
            status="different",
            diff_lines=len(diff),
            sample_diff=sample_diff,
        )

    except Exception as e:
        return FileComparison(
            relative_path=original_file.name, status="error", error=str(e)
        )


def compare_directories(original_dir: Path, written_dir: Path) -> list[FileComparison]:
    """Compare all TMDL files between two directory trees."""
    comparisons = []

    # Build file sets
    def get_tmdl_files(directory: Path) -> dict[str, Path]:
        """Get all .tmdl files with relative paths as keys."""
        files = {}
        for root, _, filenames in os.walk(directory):
            for filename in filenames:
                if filename.endswith(".tmdl"):
                    full_path = Path(root) / filename
                    rel_path = full_path.relative_to(directory)
                    files[str(rel_path)] = full_path
        return files

    original_files = get_tmdl_files(original_dir)
    written_files = get_tmdl_files(written_dir)

    # Find common, missing, and extra files
    original_keys = set(original_files.keys())
    written_keys = set(written_files.keys())

    common = original_keys & written_keys
    missing = original_keys - written_keys
    extra = written_keys - original_keys

    # Report missing files
    for rel_path in sorted(missing):
        comparisons.append(
            FileComparison(
                relative_path=rel_path,
                status="missing",
                error="File missing in written output",
            )
        )

    # Report extra files
    for rel_path in sorted(extra):
        comparisons.append(
            FileComparison(
                relative_path=rel_path,
                status="extra",
                error="Extra file in written output",
            )
        )

    # Compare common files
    for rel_path in sorted(common):
        comp = compare_files(original_files[rel_path], written_files[rel_path])
        comp.relative_path = rel_path
        comparisons.append(comp)

    return comparisons


def validate_model(
    name: str, sm_root_path: Path, output_dir: Path, verbose: bool = False
) -> ModelValidation:
    """Perform comprehensive validation of a TMDL model."""
    result = ModelValidation(name=name, original_path=str(sm_root_path))

    # Step 1: Load original TMDL
    try:
        if verbose:
            logger.info(f"Loading {name} from {sm_root_path}")

        sm = SemanticModel.read(str(sm_root_path))
        result.load_success = True

        # Count elements
        model = sm.definition.model
        result.tables = len(model.tables) if model.tables else 0
        result.relationships = (
            len(model.relationships) if model.relationships else 0
        )
        result.expressions = (
            len(model.expressions) if model.expressions else 0
        )

        for table in model.tables or []:
            result.columns += len(table.columns) if table.columns else 0
            result.measures += len(table.measures) if table.measures else 0

    except Exception as e:
        result.load_success = False
        result.load_error = f"{type(e).__name__}: {str(e)}"
        if verbose:
            result.load_error += f"\n{traceback.format_exc()}"
        return result

    # Step 2: Write to output
    try:
        output_sm_path = output_dir / name
        result.output_path = str(output_sm_path / "definition")

        if verbose:
            logger.info(f"Writing {name} to {output_sm_path}")

        sm.write(str(output_sm_path), format=FabricFormat.TMDL)
        result.write_success = True

    except Exception as e:
        result.write_success = False
        result.write_error = f"{type(e).__name__}: {str(e)}"
        if verbose:
            result.write_error += f"\n{traceback.format_exc()}"
        return result

    # Step 3: Re-read written TMDL
    try:
        if verbose:
            logger.info(f"Re-reading {name} from {output_sm_path}")

        sm_reread = SemanticModel.read(str(output_sm_path))
        result.reload_success = True

        # Verify counts match
        tables_reread = (
            len(sm_reread.definition.model.tables) if sm_reread.definition.model.tables else 0
        )
        if tables_reread != result.tables:
            result.warnings.append(
                f"Table count mismatch: original={result.tables}, reread={tables_reread}"
            )

    except Exception as e:
        result.reload_success = False
        result.reload_error = f"{type(e).__name__}: {str(e)}"
        if verbose:
            result.reload_error += f"\n{traceback.format_exc()}"
        return result

    # Step 4: Compare files
    try:
        if verbose:
            logger.info(f"Comparing files for {name}")

        original_def = sm_root_path / "definition"
        written_def = output_sm_path / "definition"
        comparisons = compare_directories(original_def, written_def)
        result.file_comparisons = comparisons
        result.files_compared = len(comparisons)

        for comp in comparisons:
            if comp.status == "identical":
                result.files_identical += 1
            elif comp.status == "different":
                result.files_different += 1
            elif comp.status == "missing":
                result.files_missing += 1
            elif comp.status == "extra":
                result.files_extra += 1

    except Exception as e:
        result.warnings.append(f"Error comparing files: {e}")
        if verbose:
            logger.error(traceback.format_exc())

    return result


def print_result(result: ModelValidation, verbose: bool = False) -> None:
    """Print validation result with color coding."""
    # Determine status
    if result.success:
        status_str = "\033[92mPASS\033[0m"
    elif (
        result.files_different > 0 or result.files_missing > 0 or result.files_extra > 0
    ):
        status_str = "\033[93mWARN\033[0m"
    else:
        status_str = "\033[91mFAIL\033[0m"

    print(f"\n[{status_str}] {result.name}")
    print(f"    Original: {result.original_path}")

    # Load stage
    if not result.load_success:
        print(f"    \033[91m✗ Load failed:\033[0m {result.load_error}")
        return
    else:
        print(
            f"    \033[92m✓ Load:\033[0m {result.tables} tables, "
            f"{result.columns} columns, {result.measures} measures, "
            f"{result.relationships} relationships, {result.expressions} expressions"
        )

    # Write stage
    if not result.write_success:
        print(f"    \033[91m✗ Write failed:\033[0m {result.write_error}")
        return
    else:
        print(f"    \033[92m✓ Write:\033[0m {result.output_path}")

    # Reload stage
    if not result.reload_success:
        print(f"    \033[91m✗ Re-read failed:\033[0m {result.reload_error}")
        return
    else:
        print(f"    \033[92m✓ Re-read:\033[0m Success")

    # File comparison
    print(
        f"    \033[94mℹ Files:\033[0m {result.files_compared} compared, "
        f"{result.files_identical} identical, "
        f"{result.files_different} different, "
        f"{result.files_missing} missing, "
        f"{result.files_extra} extra"
    )

    # Show file differences
    if result.files_different > 0:
        print(f"    \033[93m⚠ Different files:\033[0m")
        for comp in result.file_comparisons:
            if comp.status == "different":
                print(f"        - {comp.relative_path} ({comp.diff_lines} diff lines)")
                if verbose and comp.sample_diff:
                    for line in comp.sample_diff[:10]:
                        print(f"          {line}")

    if result.files_missing > 0:
        print(f"    \033[93m⚠ Missing files:\033[0m")
        for comp in result.file_comparisons:
            if comp.status == "missing":
                print(f"        - {comp.relative_path}")

    if result.files_extra > 0:
        print(f"    \033[93m⚠ Extra files:\033[0m")
        for comp in result.file_comparisons:
            if comp.status == "extra":
                print(f"        - {comp.relative_path}")

    # Show warnings
    if result.warnings:
        print(f"    \033[93m⚠ Warnings:\033[0m")
        for warning in result.warnings[:3]:
            print(f"        - {warning}")
        if len(result.warnings) > 3:
            print(f"        ... and {len(result.warnings) - 3} more")


def discover_models(samples_dir: Path) -> list[tuple[str, Path]]:
    """Discover all TMDL models in samples directory."""
    models = []

    if not samples_dir.exists():
        logger.error(f"Samples directory not found: {samples_dir}")
        return models

    for item in sorted(samples_dir.iterdir()):
        if item.is_dir():
            definition = item / "definition"
            if definition.exists() and definition.is_dir():
                models.append((item.name, item))

    return models


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Validate TMDL reading and writing")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--model", "-m", type=str, help="Validate specific model only")
    parser.add_argument(
        "--keep-output",
        "-k",
        action="store_true",
        help="Keep output directory for inspection",
    )
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.INFO)

    print_header("TMDL Detailed Validation")

    # Setup paths
    workspace = Path(__file__).parent.parent.parent
    samples_dir = workspace / "samples" / "tmdl"

    print(f"Workspace: {workspace}")
    print(f"Samples: {samples_dir}")

    # Create temp output directory
    if args.keep_output:
        output_dir = workspace / "samples" / "tmdl-validation-output"
        if output_dir.exists():
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True)
        print(f"Output: {output_dir} (will be kept)")
    else:
        output_dir = Path(tempfile.mkdtemp(prefix="tmdl_validation_"))
        print(f"Output: {output_dir} (temporary)")

    # Discover models
    models = discover_models(samples_dir)

    if not models:
        print("\n\033[91mNo TMDL models found!\033[0m")
        return 1

    # Filter if specific model requested
    if args.model:
        models = [(n, p) for n, p in models if n == args.model]
        if not models:
            print(f"\n\033[91mModel '{args.model}' not found!\033[0m")
            return 1

    print(f"\nDiscovered {len(models)} model(s):")
    for name, _ in models:
        print(f"  - {name}")

    # Validate models
    print_header(f"Validating {len(models)} Model(s)")

    results = []
    for name, sm_root_path in models:
        result = validate_model(name, sm_root_path, output_dir, args.verbose)
        results.append(result)
        print_result(result, args.verbose)

    # Summary
    print_header("Summary")

    passed = sum(1 for r in results if r.success)
    warned = sum(
        1
        for r in results
        if not r.success and r.load_success and r.write_success and r.reload_success
    )
    failed = sum(
        1
        for r in results
        if not r.load_success or not r.write_success or not r.reload_success
    )

    print(f"\nTotal: {len(results)} models validated")
    print(f"  \033[92mPassed:\033[0m {passed} (perfect roundtrip)")
    print(f"  \033[93mWarned:\033[0m {warned} (functional but file differences)")
    print(f"  \033[91mFailed:\033[0m {failed} (errors in load/write/reload)")

    # Aggregate statistics
    if results:
        total_tables = sum(r.tables for r in results if r.load_success)
        total_columns = sum(r.columns for r in results if r.load_success)
        total_measures = sum(r.measures for r in results if r.load_success)
        total_relationships = sum(r.relationships for r in results if r.load_success)
        total_files = sum(r.files_compared for r in results if r.load_success)
        total_identical = sum(r.files_identical for r in results if r.load_success)
        total_different = sum(r.files_different for r in results if r.load_success)

        print(f"\nElements validated:")
        print(f"  Tables: {total_tables}")
        print(f"  Columns: {total_columns}")
        print(f"  Measures: {total_measures}")
        print(f"  Relationships: {total_relationships}")

        print(f"\nFiles compared:")
        print(f"  Total: {total_files}")
        print(f"  Identical: {total_identical}")
        print(f"  Different: {total_different}")

    # Cleanup
    if not args.keep_output:
        try:
            shutil.rmtree(output_dir)
        except Exception as e:
            logger.warning(f"Failed to cleanup temp directory: {e}")

    # Exit code
    if failed > 0:
        print(f"\n\033[91m{failed} model(s) failed!\033[0m")
        return 1
    elif warned > 0:
        print(f"\n\033[93m{warned} model(s) have file differences!\033[0m")
        print(f"Run with --keep-output to inspect differences.")
        return 0  # Not a hard failure
    else:
        print(f"\n\033[92mAll {passed} models validated perfectly!\033[0m")
        return 0


if __name__ == "__main__":
    sys.exit(main())
