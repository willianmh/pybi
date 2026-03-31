"""
Enhanced TMDL validation script with detailed diagnostics.

This script validates the TMDL reader/writer by:
1. Loading TMDL models from samples/tmdl/ directory
2. Writing them to a temporary output directory
3. Re-reading the written files
4. Performing file-by-file text comparison
5. Reporting detailed differences and potential issues

Usage:
    uv run python scripts/validate_tmdl_reader.py
    uv run python scripts/validate_tmdl_reader.py --verbose
    uv run python scripts/validate_tmdl_reader.py --model division-sm
    uv run python scripts/validate_tmdl_reader.py --keep-output
    uv run python scripts/validate_tmdl_reader.py --analyze-only  # Only analyze, don't write
"""

import argparse
import difflib
import json
import logging
import os
import shutil
import sys
import tempfile
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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
class ParseIssue:
    """An issue found during parsing."""

    file: str
    line: int | None
    issue_type: str
    description: str
    severity: str = "warning"  # "warning", "error", "info"


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
    cultures: int = 0

    # File comparison
    files_compared: int = 0
    files_identical: int = 0
    files_different: int = 0
    files_missing: int = 0
    files_extra: int = 0

    file_comparisons: list[FileComparison] = field(default_factory=list)

    # Issues found
    parse_issues: list[ParseIssue] = field(default_factory=list)

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
    print()
    print("=" * width)
    print(f" {title}")
    print("=" * width)


def print_subheader(title: str) -> None:
    """Print a subsection header."""
    print()
    print(f"--- {title} ---")


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

        # Take first 30 lines of diff as sample
        sample_diff = [line.rstrip() for line in diff[:30]]

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

    original_keys = set(original_files.keys())
    written_keys = set(written_files.keys())

    common = original_keys & written_keys
    missing = original_keys - written_keys
    extra = written_keys - original_keys

    for rel_path in sorted(missing):
        comparisons.append(
            FileComparison(
                relative_path=rel_path,
                status="missing",
                error="File missing in written output",
            )
        )

    for rel_path in sorted(extra):
        comparisons.append(
            FileComparison(
                relative_path=rel_path,
                status="extra",
                error="Extra file in written output",
            )
        )

    for rel_path in sorted(common):
        comp = compare_files(original_files[rel_path], written_files[rel_path])
        comp.relative_path = rel_path
        comparisons.append(comp)

    return comparisons


def analyze_model(sm: Any, result: ModelValidation) -> None:
    """Analyze a loaded model for potential issues."""
    model = sm.definition.model
    # Check tables
    for table in model.tables or []:
        if not table.name:
            result.parse_issues.append(
                ParseIssue(
                    file=f"tables/{table.name or 'unknown'}.tmdl",
                    line=None,
                    issue_type="missing_name",
                    description="Table missing name",
                    severity="error",
                )
            )

        if not table.lineageTag:
            result.parse_issues.append(
                ParseIssue(
                    file=f"tables/{table.name}.tmdl",
                    line=None,
                    issue_type="missing_lineage_tag",
                    description=f"Table '{table.name}' missing lineageTag",
                    severity="warning",
                )
            )

        if not table.partitions:
            result.parse_issues.append(
                ParseIssue(
                    file=f"tables/{table.name}.tmdl",
                    line=None,
                    issue_type="no_partitions",
                    description=f"Table '{table.name}' has no partitions",
                    severity="warning",
                )
            )

        # Check columns
        for col in table.columns or []:
            if not col.name:
                result.parse_issues.append(
                    ParseIssue(
                        file=f"tables/{table.name}.tmdl",
                        line=None,
                        issue_type="missing_name",
                        description=f"Column in '{table.name}' missing name",
                        severity="error",
                    )
                )

            if not col.lineageTag:
                result.parse_issues.append(
                    ParseIssue(
                        file=f"tables/{table.name}.tmdl",
                        line=None,
                        issue_type="missing_lineage_tag",
                        description=f"Column '{col.name}' in '{table.name}' missing lineageTag",
                        severity="info",
                    )
                )

        # Check measures
        for measure in table.measures or []:
            if not measure.name:
                result.parse_issues.append(
                    ParseIssue(
                        file=f"tables/{table.name}.tmdl",
                        line=None,
                        issue_type="missing_name",
                        description=f"Measure in '{table.name}' missing name",
                        severity="error",
                    )
                )

            if not measure.expression:
                result.parse_issues.append(
                    ParseIssue(
                        file=f"tables/{table.name}.tmdl",
                        line=None,
                        issue_type="empty_expression",
                        description=f"Measure '{measure.name}' in '{table.name}' has empty expression",
                        severity="warning",
                    )
                )

            # Check for special characters in measure names that might cause parsing issues
            if measure.name and ("(" in measure.name or ")" in measure.name):
                result.parse_issues.append(
                    ParseIssue(
                        file=f"tables/{table.name}.tmdl",
                        line=None,
                        issue_type="special_chars_in_name",
                        description=f"Measure '{measure.name}' has parentheses in name - may need quoting",
                        severity="info",
                    )
                )

    # Check relationships
    for rel in model.relationships or []:
        if not rel.name:
            result.parse_issues.append(
                ParseIssue(
                    file="relationships.tmdl",
                    line=None,
                    issue_type="missing_name",
                    description="Relationship missing name",
                    severity="error",
                )
            )

        if not rel.fromTable or not rel.fromColumn:
            result.parse_issues.append(
                ParseIssue(
                    file="relationships.tmdl",
                    line=None,
                    issue_type="incomplete_relationship",
                    description=f"Relationship '{rel.name}' missing fromTable/fromColumn",
                    severity="warning",
                )
            )

        if not rel.toTable or not rel.toColumn:
            result.parse_issues.append(
                ParseIssue(
                    file="relationships.tmdl",
                    line=None,
                    issue_type="incomplete_relationship",
                    description=f"Relationship '{rel.name}' missing toTable/toColumn",
                    severity="warning",
                )
            )


def validate_model(
    name: str,
    sm_root_path: Path,
    output_dir: Path | None,
    verbose: bool = False,
    analyze_only: bool = False,
) -> ModelValidation:
    """Perform comprehensive validation of a TMDL model."""
    # Import here to avoid startup delay
    from poupytempo import SemanticModel
    from poupytempo.utils.enums import FabricFormat

    result = ModelValidation(name=name, original_path=str(sm_root_path))

    # Step 1: Load original TMDL
    try:
        if verbose:
            print(f"  Loading {name} from {sm_root_path}")

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
        result.cultures = len(model.cultures) if model.cultures else 0

        for table in model.tables or []:
            result.columns += len(table.columns) if table.columns else 0
            result.measures += len(table.measures) if table.measures else 0

        # Analyze for issues
        analyze_model(sm, result)

    except Exception as e:
        result.load_success = False
        result.load_error = f"{type(e).__name__}: {str(e)}"
        if verbose:
            result.load_error += f"\n{traceback.format_exc()}"
        return result

    if analyze_only:
        return result

    if output_dir is None:
        return result

    # Step 2: Write to output
    try:
        output_sm_path = output_dir / name
        result.output_path = str(output_sm_path / "definition")

        if verbose:
            print(f"  Writing {name} to {output_sm_path}")

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
            print(f"  Re-reading {name} from {output_sm_path}")

        sm_reread = SemanticModel.read(str(output_sm_path))
        result.reload_success = True

        # Verify counts match
        tables_reread = (
            len(sm_reread.definition.model.tables) if sm_reread.definition.model.tables else 0
        )
        if tables_reread != result.tables:
            result.parse_issues.append(
                ParseIssue(
                    file="<reloaded>",
                    line=None,
                    issue_type="count_mismatch",
                    description=f"Table count mismatch: original={result.tables}, reread={tables_reread}",
                    severity="error",
                )
            )

        rels_reread = (
            len(sm_reread.definition.model.relationships)
            if sm_reread.definition.model.relationships
            else 0
        )
        if rels_reread != result.relationships:
            result.parse_issues.append(
                ParseIssue(
                    file="<reloaded>",
                    line=None,
                    issue_type="count_mismatch",
                    description=f"Relationship count mismatch: original={result.relationships}, reread={rels_reread}",
                    severity="error",
                )
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
            print(f"  Comparing files for {name}")

        comparisons = compare_directories(sm_root_path / "definition", output_sm_path / "definition")
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
        result.parse_issues.append(
            ParseIssue(
                file="<comparison>",
                line=None,
                issue_type="comparison_error",
                description=f"Error comparing files: {e}",
                severity="error",
            )
        )
        if verbose:
            logger.error(traceback.format_exc())

    return result


def print_result(result: ModelValidation, verbose: bool = False) -> None:
    """Print validation result."""
    # Determine status
    if result.success:
        status_str = "[PASS]"
    elif (
        result.files_different > 0 or result.files_missing > 0 or result.files_extra > 0
    ):
        status_str = "[WARN]"
    else:
        status_str = "[FAIL]"

    print(f"\n{status_str} {result.name}")
    print(f"    Original: {result.original_path}")

    # Load stage
    if not result.load_success:
        print(f"    [X] Load failed: {result.load_error}")
        return
    else:
        print(
            f"    [+] Load: {result.tables} tables, "
            f"{result.columns} columns, {result.measures} measures, "
            f"{result.relationships} relationships, {result.expressions} expressions"
        )

    # Write stage
    if result.output_path:
        if not result.write_success:
            print(f"    [X] Write failed: {result.write_error}")
            return
        else:
            print(f"    [+] Write: {result.output_path}")

        # Reload stage
        if not result.reload_success:
            print(f"    [X] Re-read failed: {result.reload_error}")
            return
        else:
            print(f"    [+] Re-read: Success")

        # File comparison
        print(
            f"    [i] Files: {result.files_compared} compared, "
            f"{result.files_identical} identical, "
            f"{result.files_different} different, "
            f"{result.files_missing} missing, "
            f"{result.files_extra} extra"
        )

        # Show file differences
        if result.files_different > 0:
            print(f"    [!] Different files:")
            for comp in result.file_comparisons:
                if comp.status == "different":
                    print(
                        f"        - {comp.relative_path} ({comp.diff_lines} diff lines)"
                    )
                    if verbose and comp.sample_diff:
                        for line in comp.sample_diff[:15]:
                            print(f"          {line}")

        if result.files_missing > 0:
            print(f"    [!] Missing files:")
            for comp in result.file_comparisons:
                if comp.status == "missing":
                    print(f"        - {comp.relative_path}")

        if result.files_extra > 0:
            print(f"    [!] Extra files:")
            for comp in result.file_comparisons:
                if comp.status == "extra":
                    print(f"        - {comp.relative_path}")

    # Show parse issues
    errors = [i for i in result.parse_issues if i.severity == "error"]
    warnings = [i for i in result.parse_issues if i.severity == "warning"]

    if errors:
        print(f"    [!] Errors ({len(errors)}):")
        for issue in errors[:5]:
            print(f"        - {issue.description}")
        if len(errors) > 5:
            print(f"        ... and {len(errors) - 5} more")

    if warnings and verbose:
        print(f"    [!] Warnings ({len(warnings)}):")
        for issue in warnings[:5]:
            print(f"        - {issue.description}")
        if len(warnings) > 5:
            print(f"        ... and {len(warnings) - 5} more")


def discover_models(samples_dir: Path) -> list[tuple[str, Path]]:
    """Discover all TMDL models in samples directory."""
    models = []

    if not samples_dir.exists():
        logger.error(f"Samples directory not found: {samples_dir}")
        return models

    for item in sorted(samples_dir.iterdir()):
        if item.is_dir() and not item.name.endswith("-output"):
            definition = item / "definition"
            if definition.exists() and definition.is_dir():
                models.append((item.name, item))

    return models


def write_detailed_report(results: list[ModelValidation], output_path: Path) -> None:
    """Write a detailed JSON report of all validation results."""
    report = {
        "summary": {
            "total_models": len(results),
            "passed": sum(1 for r in results if r.success),
            "warned": sum(1 for r in results if not r.success and r.load_success),
            "failed": sum(1 for r in results if not r.load_success),
            "total_tables": sum(r.tables for r in results if r.load_success),
            "total_columns": sum(r.columns for r in results if r.load_success),
            "total_measures": sum(r.measures for r in results if r.load_success),
            "total_relationships": sum(
                r.relationships for r in results if r.load_success
            ),
        },
        "models": [],
    }

    for result in results:
        model_report = {
            "name": result.name,
            "original_path": result.original_path,
            "load_success": result.load_success,
            "write_success": result.write_success,
            "reload_success": result.reload_success,
            "statistics": {
                "tables": result.tables,
                "columns": result.columns,
                "measures": result.measures,
                "relationships": result.relationships,
                "expressions": result.expressions,
            },
            "file_comparison": {
                "total": result.files_compared,
                "identical": result.files_identical,
                "different": result.files_different,
                "missing": result.files_missing,
                "extra": result.files_extra,
            },
            "different_files": [
                {
                    "path": comp.relative_path,
                    "diff_lines": comp.diff_lines,
                }
                for comp in result.file_comparisons
                if comp.status == "different"
            ],
            "issues": [
                {
                    "file": issue.file,
                    "type": issue.issue_type,
                    "description": issue.description,
                    "severity": issue.severity,
                }
                for issue in result.parse_issues
            ],
        }

        if result.load_error:
            model_report["load_error"] = result.load_error
        if result.write_error:
            model_report["write_error"] = result.write_error
        if result.reload_error:
            model_report["reload_error"] = result.reload_error

        report["models"].append(model_report)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"\nDetailed report written to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Validate TMDL reading and writing")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Verbose output with diffs"
    )
    parser.add_argument("--model", "-m", type=str, help="Validate specific model only")
    parser.add_argument(
        "--keep-output",
        "-k",
        action="store_true",
        help="Keep output directory for inspection",
    )
    parser.add_argument(
        "--analyze-only",
        "-a",
        action="store_true",
        help="Only analyze (load), don't write/compare",
    )
    parser.add_argument(
        "--report", "-r", type=str, help="Write detailed JSON report to file"
    )
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.INFO)

    print_header("TMDL Reader Validation")

    # Setup paths
    workspace = Path(__file__).parent.parent.parent
    samples_dir = workspace / "samples" / "tmdl"

    print(f"Workspace: {workspace}")
    print(f"Samples: {samples_dir}")

    # Create temp output directory
    output_dir = None
    if not args.analyze_only:
        if args.keep_output:
            output_dir = workspace / "samples" / "tmdl-validation-output"
            if output_dir.exists():
                shutil.rmtree(output_dir)
            output_dir.mkdir(parents=True)
            print(f"Output: {output_dir} (will be kept)")
        else:
            output_dir = Path(tempfile.mkdtemp(prefix="tmdl_validation_"))
            print(f"Output: {output_dir} (temporary)")
    else:
        print("Mode: Analyze only (no write/compare)")

    # Discover models
    models = discover_models(samples_dir)

    if not models:
        print("\n[!] No TMDL models found!")
        return 1

    # Filter if specific model requested
    if args.model:
        models = [(n, p) for n, p in models if n == args.model]
        if not models:
            print(f"\n[!] Model '{args.model}' not found!")
            return 1

    print(f"\nDiscovered {len(models)} model(s):")
    for name, _ in models:
        print(f"  - {name}")

    # Validate models
    print_header(f"Validating {len(models)} Model(s)")

    results = []
    for name, sm_root_path in models:
        result = validate_model(
            name, sm_root_path, output_dir, args.verbose, args.analyze_only
        )
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
    print(f"  Passed: {passed} (perfect roundtrip)")
    print(f"  Warned: {warned} (functional but file differences)")
    print(f"  Failed: {failed} (errors in load/write/reload)")

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

        if not args.analyze_only:
            print(f"\nFiles compared:")
            print(f"  Total: {total_files}")
            print(f"  Identical: {total_identical}")
            print(f"  Different: {total_different}")

        # Aggregate issues
        all_errors = []
        all_warnings = []
        for r in results:
            for issue in r.parse_issues:
                if issue.severity == "error":
                    all_errors.append((r.name, issue))
                elif issue.severity == "warning":
                    all_warnings.append((r.name, issue))

        if all_errors:
            print(f"\nTotal errors: {len(all_errors)}")
        if all_warnings:
            print(f"Total warnings: {len(all_warnings)}")

    # Write detailed report if requested
    if args.report:
        report_path = Path(args.report)
        write_detailed_report(results, report_path)

    # Cleanup
    if output_dir and not args.keep_output and not args.analyze_only:
        try:
            shutil.rmtree(output_dir)
        except Exception as e:
            logger.warning(f"Failed to cleanup temp directory: {e}")

    # Exit code
    if failed > 0:
        print(f"\n{failed} model(s) failed!")
        return 1
    elif warned > 0:
        print(f"\n{warned} model(s) have file differences!")
        if not args.keep_output and not args.analyze_only:
            print("Run with --keep-output to inspect differences.")
        return 0
    else:
        print(f"\nAll {passed} models validated successfully!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
