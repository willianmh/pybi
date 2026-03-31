"""
Validates pybi serialization/deserialization against real production files.

Discovers SemanticModel and Report artifacts in a workspace folder, reads them
using pybi's auto-detecting read() methods (TMDL, model.bim, PBIR, legacy),
validates structural integrity, and performs round-trip testing (write to temp
directory, re-read, compare structural counts).

Usage:
    uv run python scripts/validate_production.py
    uv run python scripts/validate_production.py --workspace /path/to/workspace
    uv run python scripts/validate_production.py --samples
    uv run python scripts/validate_production.py --verbose
    uv run python scripts/validate_production.py --no-roundtrip
"""

import argparse
import logging
import os
import sys
import tempfile
import traceback
from dataclasses import dataclass, field
from pathlib import Path

from pybi.report.legacy.legacy_model import ReportJsonDefinition
from pybi.report.pbir.definition import PbirReportDefinition
from pybi.report.report import Report
from pybi.semanticmodel.semanticmodel import SemanticModel

DEFAULT_WORKSPACE = r"C:\Users\haw4ca\Documents\code\pbi_workspace"
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
SAMPLES_DIR = REPO_ROOT / "samples"

logger = logging.getLogger("validate_production")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ArtifactCounts:
    """Countable structural elements extracted from an artifact."""

    # SemanticModel counts
    tables: int = 0
    columns: int = 0
    measures: int = 0
    relationships: int = 0
    expressions: int = 0
    partitions: int = 0

    # Report counts
    pages: int = 0
    visuals: int = 0
    bookmarks: int = 0


@dataclass
class ValidationResult:
    """Result of validating a single artifact."""

    artifact_type: str  # "SemanticModel" or "Report"
    name: str
    path: str
    format: str  # e.g. "TMDL", "model.bim", "PBIR", "report.json"
    success: bool = False
    counts: ArtifactCounts = field(default_factory=ArtifactCounts)
    warnings: list[str] = field(default_factory=list)
    error: str | None = None
    error_traceback: str | None = None
    roundtrip_success: bool | None = None  # None = not attempted
    roundtrip_error: str | None = None
    roundtrip_error_traceback: str | None = None
    roundtrip_mismatches: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def discover_artifacts(workspace_path: str | Path) -> tuple[list[Path], list[Path]]:
    """
    Recursively discover SemanticModel and Report folders in a workspace.

    Returns:
        (semantic_model_paths, report_paths)
    """
    workspace = Path(workspace_path)
    if not workspace.exists():
        logger.error("Workspace path does not exist: %s", workspace)
        return [], []

    semantic_models: list[Path] = []
    reports: list[Path] = []

    for dirpath, dirnames, _ in os.walk(workspace):
        # Skip hidden/internal folders
        dirnames[:] = [
            d
            for d in dirnames
            if not d.startswith(".")
            and d != "__pycache__"
            and d != ".git"
        ]

        current = Path(dirpath)
        name = current.name

        if name.endswith(".SemanticModel") or name.endswith(".Dataset"):
            semantic_models.append(current)
            dirnames.clear()  # Don't recurse into the artifact itself
        elif name.endswith(".Report"):
            reports.append(current)
            dirnames.clear()

    return semantic_models, reports


# ---------------------------------------------------------------------------
# Counting helpers
# ---------------------------------------------------------------------------


def count_semantic_model(sm: SemanticModel) -> ArtifactCounts:
    """Extract structural counts from a SemanticModel."""
    model = sm.definition.model
    counts = ArtifactCounts()

    counts.tables = len(model.tables) if model.tables else 0
    counts.relationships = len(model.relationships) if model.relationships else 0
    counts.expressions = len(model.expressions) if model.expressions else 0

    for table in model.tables or []:
        counts.columns += len(table.columns) if table.columns else 0
        counts.measures += len(table.measures) if table.measures else 0
        counts.partitions += len(table.partitions) if table.partitions else 0

    return counts


def count_report(report: Report) -> ArtifactCounts:
    """Extract structural counts from a Report."""
    counts = ArtifactCounts()
    defn = report.definition

    if isinstance(defn, PbirReportDefinition):
        counts.pages = len(defn.pages)
        counts.visuals = sum(len(p.visuals) for p in defn.pages)
        counts.bookmarks = len(defn.bookmarks)
    elif isinstance(defn, ReportJsonDefinition):
        counts.pages = len(defn.sections)
        counts.visuals = sum(len(s.visualContainers) for s in defn.sections)
        counts.bookmarks = len(defn.config.bookmarks) if defn.config.bookmarks else 0

    return counts


# ---------------------------------------------------------------------------
# Structural validation
# ---------------------------------------------------------------------------


def validate_semantic_model_structure(sm: SemanticModel) -> list[str]:
    """Check key structural invariants on a SemanticModel. Returns warnings."""
    warnings: list[str] = []
    model = sm.definition.model

    for table in model.tables or []:
        if not table.name:
            warnings.append("Table with missing name found")
        if not table.partitions:
            warnings.append(f"Table '{table.name}' has no partitions")
        if not table.lineageTag:
            warnings.append(f"Table '{table.name}' missing lineageTag")

        for col in table.columns or []:
            if not col.name:
                warnings.append(f"Column in table '{table.name}' missing name")
            if not col.dataType:
                warnings.append(
                    f"Column '{col.name}' in table '{table.name}' missing dataType"
                )

        for measure in table.measures or []:
            if not measure.name:
                warnings.append(f"Measure in table '{table.name}' missing name")
            if not measure.expression:
                warnings.append(
                    f"Measure '{measure.name}' in table '{table.name}' missing expression"
                )

    for rel in model.relationships or []:
        if not rel.name:
            warnings.append("Relationship with missing name found")
        if not rel.fromTable or not rel.fromColumn:
            warnings.append(
                f"Relationship '{rel.name}' missing fromTable/fromColumn"
            )
        if not rel.toTable or not rel.toColumn:
            warnings.append(
                f"Relationship '{rel.name}' missing toTable/toColumn"
            )

    return warnings


def validate_report_structure(report: Report) -> list[str]:
    """Check key structural invariants on a Report. Returns warnings."""
    warnings: list[str] = []
    defn = report.definition

    if isinstance(defn, PbirReportDefinition):
        if not defn.pages:
            warnings.append("PBIR report has no pages")
        for i, page_with_visuals in enumerate(defn.pages):
            page = page_with_visuals.page
            if hasattr(page, "name") and not page.name:
                warnings.append(f"Page {i} missing name")
            if hasattr(page, "displayName") and not page.displayName:
                warnings.append(f"Page {i} missing displayName")

    elif isinstance(defn, ReportJsonDefinition):
        if not defn.sections:
            warnings.append("Legacy report has no sections (pages)")
        for i, section in enumerate(defn.sections):
            if not section.name:
                warnings.append(f"Section {i} missing name")
            if not section.displayName:
                warnings.append(f"Section {i} missing displayName")

    return warnings


# ---------------------------------------------------------------------------
# Read validation
# ---------------------------------------------------------------------------


def validate_semantic_model(path: Path) -> ValidationResult:
    """Read and validate a SemanticModel artifact."""
    name = path.name.rsplit(".", 1)[0]  # Remove .SemanticModel / .Dataset suffix
    result = ValidationResult(
        artifact_type="SemanticModel",
        name=name,
        path=str(path),
        format="unknown",
    )

    try:
        logger.info("Reading SemanticModel: %s", path)
        sm = SemanticModel.read(path)
        fmt = sm._source_format
        result.format = fmt.name if fmt else "unknown"
        logger.info("  Format detected: %s", result.format)

        # Count elements
        result.counts = count_semantic_model(sm)
        logger.info(
            "  Tables: %d, Columns: %d, Measures: %d, Relationships: %d, "
            "Expressions: %d, Partitions: %d",
            result.counts.tables,
            result.counts.columns,
            result.counts.measures,
            result.counts.relationships,
            result.counts.expressions,
            result.counts.partitions,
        )

        # Structural validation
        result.warnings = validate_semantic_model_structure(sm)
        if result.warnings:
            logger.info("  Warnings: %d", len(result.warnings))
            for w in result.warnings:
                logger.debug("    - %s", w)

        result.success = True

        # Store for round-trip (returned via closure-like reference)
        result._sm = sm  # type: ignore[attr-defined]

    except Exception as e:
        result.error = f"{type(e).__name__}: {e}"
        result.error_traceback = traceback.format_exc()
        logger.error("  FAILED: %s", result.error)
        logger.debug("  Traceback:\n%s", result.error_traceback)

    return result


def validate_report(path: Path) -> ValidationResult:
    """Read and validate a Report artifact."""
    name = path.name.rsplit(".", 1)[0]  # Remove .Report suffix
    result = ValidationResult(
        artifact_type="Report",
        name=name,
        path=str(path),
        format="unknown",
    )

    try:
        logger.info("Reading Report: %s", path)
        report = Report.read(path)
        fmt = report._source_format
        result.format = fmt.name if fmt else "unknown"
        logger.info("  Format detected: %s", result.format)

        # Count elements
        result.counts = count_report(report)
        logger.info(
            "  Pages: %d, Visuals: %d, Bookmarks: %d",
            result.counts.pages,
            result.counts.visuals,
            result.counts.bookmarks,
        )

        # Structural validation
        result.warnings = validate_report_structure(report)
        if result.warnings:
            logger.info("  Warnings: %d", len(result.warnings))
            for w in result.warnings:
                logger.debug("    - %s", w)

        result.success = True

        # Store for round-trip
        result._report = report  # type: ignore[attr-defined]

    except Exception as e:
        result.error = f"{type(e).__name__}: {e}"
        result.error_traceback = traceback.format_exc()
        logger.error("  FAILED: %s", result.error)
        logger.debug("  Traceback:\n%s", result.error_traceback)

    return result


# ---------------------------------------------------------------------------
# Round-trip validation
# ---------------------------------------------------------------------------


def roundtrip_semantic_model(result: ValidationResult) -> None:
    """Write a SemanticModel to a temp dir, re-read, and compare counts."""
    sm: SemanticModel = result._sm  # type: ignore[attr-defined]

    try:
        with tempfile.TemporaryDirectory(prefix="pybi_validate_sm_") as tmp:
            out_path = Path(tmp) / "RoundTrip.SemanticModel"
            logger.info("  Round-trip: writing to %s", out_path)
            sm.write(root_path=out_path, format=sm._source_format)

            logger.info("  Round-trip: re-reading from %s", out_path)
            sm2 = SemanticModel.read(out_path)
            counts2 = count_semantic_model(sm2)

            # Compare
            mismatches: list[str] = []
            for attr in ("tables", "columns", "measures", "relationships", "expressions", "partitions"):
                orig = getattr(result.counts, attr)
                rt = getattr(counts2, attr)
                if orig != rt:
                    mismatches.append(f"{attr}: {orig} -> {rt}")

            if mismatches:
                result.roundtrip_success = False
                result.roundtrip_mismatches = mismatches
                logger.error("  Round-trip MISMATCH:")
                for m in mismatches:
                    logger.error("    %s", m)
            else:
                result.roundtrip_success = True
                logger.info("  Round-trip: OK (all counts match)")

    except Exception as e:
        result.roundtrip_success = False
        result.roundtrip_error = f"{type(e).__name__}: {e}"
        result.roundtrip_error_traceback = traceback.format_exc()
        logger.error("  Round-trip FAILED: %s", result.roundtrip_error)
        logger.debug("  Traceback:\n%s", result.roundtrip_error_traceback)


def roundtrip_report(result: ValidationResult) -> None:
    """Write a Report to a temp dir, re-read, and compare counts."""
    report: Report = result._report  # type: ignore[attr-defined]

    try:
        with tempfile.TemporaryDirectory(prefix="pybi_validate_rpt_") as tmp:
            out_path = Path(tmp) / "RoundTrip.Report"
            logger.info("  Round-trip: writing to %s", out_path)
            report.write(root_path=out_path, format=report._source_format)

            logger.info("  Round-trip: re-reading from %s", out_path)
            report2 = Report.read(out_path)
            counts2 = count_report(report2)

            # Compare
            mismatches: list[str] = []
            for attr in ("pages", "visuals", "bookmarks"):
                orig = getattr(result.counts, attr)
                rt = getattr(counts2, attr)
                if orig != rt:
                    mismatches.append(f"{attr}: {orig} -> {rt}")

            if mismatches:
                result.roundtrip_success = False
                result.roundtrip_mismatches = mismatches
                logger.error("  Round-trip MISMATCH:")
                for m in mismatches:
                    logger.error("    %s", m)
            else:
                result.roundtrip_success = True
                logger.info("  Round-trip: OK (all counts match)")

    except Exception as e:
        result.roundtrip_success = False
        result.roundtrip_error = f"{type(e).__name__}: {e}"
        result.roundtrip_error_traceback = traceback.format_exc()
        logger.error("  Round-trip FAILED: %s", result.roundtrip_error)
        logger.debug("  Traceback:\n%s", result.roundtrip_error_traceback)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

# ANSI color codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_header(title: str) -> None:
    print(f"\n{BOLD}{'=' * 78}{RESET}")
    print(f"{BOLD} {title}{RESET}")
    print(f"{BOLD}{'=' * 78}{RESET}")


def print_result_line(result: ValidationResult) -> None:
    """Print a one-line summary for a single result."""
    if result.success:
        status = f"{GREEN}PASS{RESET}"
    else:
        status = f"{RED}FAIL{RESET}"

    rt_status = ""
    if result.roundtrip_success is True:
        rt_status = f"  RT:{GREEN}OK{RESET}"
    elif result.roundtrip_success is False:
        rt_status = f"  RT:{RED}FAIL{RESET}"

    print(f"  [{status}] {result.name} ({result.format}){rt_status}")


def print_detailed_result(result: ValidationResult) -> None:
    """Print full details for a single result."""
    if result.success:
        status = f"{GREEN}PASS{RESET}"
    else:
        status = f"{RED}FAIL{RESET}"

    print(f"\n  [{status}] {result.artifact_type}: {result.name}")
    print(f"    Path:   {result.path}")
    print(f"    Format: {result.format}")

    if result.success:
        c = result.counts
        if result.artifact_type == "SemanticModel":
            print(
                f"    Tables: {c.tables}  Columns: {c.columns}  "
                f"Measures: {c.measures}  Relationships: {c.relationships}  "
                f"Expressions: {c.expressions}  Partitions: {c.partitions}"
            )
        else:
            print(
                f"    Pages: {c.pages}  Visuals: {c.visuals}  "
                f"Bookmarks: {c.bookmarks}"
            )
    else:
        print(f"    {RED}Error: {result.error}{RESET}")
        if result.error_traceback:
            for line in result.error_traceback.strip().splitlines():
                print(f"    {RED}| {line}{RESET}")

    if result.warnings:
        shown = result.warnings[:10]
        for w in shown:
            print(f"    {YELLOW}Warning: {w}{RESET}")
        remaining = len(result.warnings) - len(shown)
        if remaining > 0:
            print(f"    {YELLOW}... and {remaining} more warning(s){RESET}")

    # Round-trip details
    if result.roundtrip_success is True:
        print(f"    Round-trip: {GREEN}OK{RESET}")
    elif result.roundtrip_success is False:
        if result.roundtrip_mismatches:
            print(f"    Round-trip: {RED}MISMATCH{RESET}")
            for m in result.roundtrip_mismatches:
                print(f"      {RED}{m}{RESET}")
        if result.roundtrip_error:
            print(f"    Round-trip: {RED}ERROR: {result.roundtrip_error}{RESET}")
            if result.roundtrip_error_traceback:
                for line in result.roundtrip_error_traceback.strip().splitlines():
                    print(f"      {RED}| {line}{RESET}")


def print_summary(results: list[ValidationResult]) -> None:
    """Print the final summary."""
    print_header("Summary")

    sm_results = [r for r in results if r.artifact_type == "SemanticModel"]
    rpt_results = [r for r in results if r.artifact_type == "Report"]

    def _group_summary(label: str, subset: list[ValidationResult]) -> None:
        if not subset:
            return

        total = len(subset)
        passed = sum(1 for r in subset if r.success)
        failed = total - passed

        rt_tested = [r for r in subset if r.roundtrip_success is not None]
        rt_passed = sum(1 for r in rt_tested if r.roundtrip_success)
        rt_failed = len(rt_tested) - rt_passed

        # Group by format
        formats: dict[str, list[ValidationResult]] = {}
        for r in subset:
            formats.setdefault(r.format, []).append(r)

        print(f"\n  {BOLD}{label}{RESET}: {total} total, "
              f"{GREEN}{passed} passed{RESET}, "
              f"{RED}{failed} failed{RESET}")

        for fmt, fmt_results in sorted(formats.items()):
            fmt_passed = sum(1 for r in fmt_results if r.success)
            fmt_failed = len(fmt_results) - fmt_passed
            print(f"    {fmt}: {len(fmt_results)} total, "
                  f"{fmt_passed} passed, {fmt_failed} failed")

        if rt_tested:
            print(f"    Round-trip: {len(rt_tested)} tested, "
                  f"{GREEN}{rt_passed} passed{RESET}, "
                  f"{RED}{rt_failed} failed{RESET}")

    _group_summary("SemanticModel", sm_results)
    _group_summary("Report", rpt_results)

    # Aggregate element totals
    print(f"\n  {BOLD}Total elements loaded:{RESET}")

    total_tables = sum(r.counts.tables for r in sm_results if r.success)
    total_columns = sum(r.counts.columns for r in sm_results if r.success)
    total_measures = sum(r.counts.measures for r in sm_results if r.success)
    total_relationships = sum(r.counts.relationships for r in sm_results if r.success)
    total_expressions = sum(r.counts.expressions for r in sm_results if r.success)
    total_partitions = sum(r.counts.partitions for r in sm_results if r.success)
    total_pages = sum(r.counts.pages for r in rpt_results if r.success)
    total_visuals = sum(r.counts.visuals for r in rpt_results if r.success)
    total_bookmarks = sum(r.counts.bookmarks for r in rpt_results if r.success)

    print(f"    SemanticModel — Tables: {total_tables}, Columns: {total_columns}, "
          f"Measures: {total_measures}, Relationships: {total_relationships}, "
          f"Expressions: {total_expressions}, Partitions: {total_partitions}")
    print(f"    Report — Pages: {total_pages}, Visuals: {total_visuals}, "
          f"Bookmarks: {total_bookmarks}")

    # Final verdict
    all_read_passed = all(r.success for r in results)
    all_rt_passed = all(
        r.roundtrip_success is not False for r in results
    )

    total_failures = sum(1 for r in results if not r.success)
    total_rt_failures = sum(1 for r in results if r.roundtrip_success is False)

    print()
    if all_read_passed and all_rt_passed:
        print(f"  {GREEN}{BOLD}All {len(results)} artifact(s) validated successfully!{RESET}")
    else:
        if total_failures:
            print(f"  {RED}{BOLD}{total_failures} artifact(s) failed read validation.{RESET}")
        if total_rt_failures:
            print(f"  {RED}{BOLD}{total_rt_failures} artifact(s) failed round-trip validation.{RESET}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate pybi serialization against production files."
    )
    parser.add_argument(
        "--workspace",
        default=DEFAULT_WORKSPACE,
        help=f"Path to the workspace folder to scan (default: {DEFAULT_WORKSPACE})",
    )
    parser.add_argument(
        "--samples",
        action="store_true",
        help="Validate the repo's samples/ folder instead of the workspace",
    )
    parser.add_argument(
        "--no-roundtrip",
        action="store_true",
        help="Skip round-trip (write → re-read → compare) validation",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed output including warnings and tracebacks",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Show maximum debug output",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    # Configure logging
    if args.debug:
        log_level = logging.DEBUG
    elif args.verbose:
        log_level = logging.INFO
    else:
        log_level = logging.WARNING

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    # Determine workspace
    if args.samples:
        workspace = str(SAMPLES_DIR)
    else:
        workspace = args.workspace

    print_header("pybi Production Validation")
    print(f"  Workspace: {workspace}")
    print(f"  Round-trip: {'disabled' if args.no_roundtrip else 'enabled'}")
    print(f"  Verbosity: {'debug' if args.debug else 'verbose' if args.verbose else 'normal'}")

    # Phase 1: Discovery
    print_header("Phase 1: Discovery")

    sm_paths, rpt_paths = discover_artifacts(workspace)

    print(f"\n  Found {len(sm_paths)} SemanticModel(s):")
    for p in sorted(sm_paths):
        print(f"    {p}")

    print(f"\n  Found {len(rpt_paths)} Report(s):")
    for p in sorted(rpt_paths):
        print(f"    {p}")

    if not sm_paths and not rpt_paths:
        print(f"\n  {RED}No artifacts found. Check the workspace path.{RESET}")
        return 1

    results: list[ValidationResult] = []

    # Phase 2: Read Validation — SemanticModels
    if sm_paths:
        print_header(f"Phase 2a: Validate SemanticModels ({len(sm_paths)})")
        for path in sorted(sm_paths):
            result = validate_semantic_model(path)
            results.append(result)
            print_detailed_result(result)

    # Phase 2: Read Validation — Reports
    if rpt_paths:
        print_header(f"Phase 2b: Validate Reports ({len(rpt_paths)})")
        for path in sorted(rpt_paths):
            result = validate_report(path)
            results.append(result)
            print_detailed_result(result)

    # Phase 3: Round-trip validation
    if not args.no_roundtrip:
        roundtrip_candidates = [r for r in results if r.success]
        if roundtrip_candidates:
            print_header(
                f"Phase 3: Round-Trip Validation ({len(roundtrip_candidates)})"
            )
            for result in roundtrip_candidates:
                print(f"\n  {result.artifact_type}: {result.name} ({result.format})")
                if result.artifact_type == "SemanticModel":
                    roundtrip_semantic_model(result)
                else:
                    roundtrip_report(result)

                # Print round-trip status inline
                if result.roundtrip_success is True:
                    print(f"    {GREEN}Round-trip: OK{RESET}")
                elif result.roundtrip_success is False:
                    print(f"    {RED}Round-trip: FAILED{RESET}")
                    if result.roundtrip_mismatches:
                        for m in result.roundtrip_mismatches:
                            print(f"      {RED}{m}{RESET}")
                    if result.roundtrip_error:
                        print(f"      {RED}{result.roundtrip_error}{RESET}")
                        if result.roundtrip_error_traceback and (args.verbose or args.debug):
                            for line in result.roundtrip_error_traceback.strip().splitlines():
                                print(f"      {RED}| {line}{RESET}")

    # Phase 4: Summary
    print_summary(results)

    # Compact results table
    print_header("Results")
    for result in results:
        print_result_line(result)

    # Exit code
    has_failures = any(not r.success for r in results)
    has_rt_failures = any(r.roundtrip_success is False for r in results)
    return 1 if (has_failures or has_rt_failures) else 0


if __name__ == "__main__":
    sys.exit(main())
