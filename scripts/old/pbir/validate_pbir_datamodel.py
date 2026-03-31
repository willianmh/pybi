"""
Validates the PBIR data-model (generated Pydantic classes) against real report files.

Two-tier approach mirrors validate_against_files_production.py for TMDL:

  Tier 1 — Pipeline load (permissive)
    Uses PbirStrategy + LocalTransport (PbirVisualContainer, extra='allow') to
    verify the full deserialization pipeline can ingest every report.

  Tier 2 — Strict model validation (generated schemas)
        Parses every visual.json with the *strict* generated VisualContainer matching
        that file's ``$schema`` version (currently 2.3.0 and 2.4.0), and every
        filterConfig block with
    FilterConfiguration (filterconfiguration/v1.2.0, extra='forbid').
    This catches regressions in the generated models.

Usage:
    uv run python scripts/pbir/validate_pbir_datamodel.py
    uv run python scripts/pbir/validate_pbir_datamodel.py --verbose
    uv run python scripts/pbir/validate_pbir_datamodel.py --tier1-only
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLES_PATH = _REPO_ROOT / "samples" / "pbir"

# ---------------------------------------------------------------------------
# Lazy imports — avoid crashing if something is missing at module level
# ---------------------------------------------------------------------------

def _import_pipeline():
    from poupytempo.persistence.strategies.pbir import PbirStrategy
    from poupytempo.persistence.transports.local import LocalTransport
    return PbirStrategy, LocalTransport


def _import_strict_models():
    from poupytempo.report.pbir.models import init_visual_container_for_schema
    from poupytempo.report.models.filterconfiguration.v1_2_0.model import FilterConfiguration
    return init_visual_container_for_schema, FilterConfiguration


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class VisualResult:
    page_name: str
    visual_id: str
    tier1_ok: bool = False
    tier1_error: str | None = None
    tier2_ok: bool = False
    tier2_error: str | None = None
    filter_ok: bool = False
    filter_error: str | None = None
    has_filter: bool = False


@dataclass
class PageResult:
    page_id: str
    display_name: str
    visual_count: int = 0
    visuals: list[VisualResult] = field(default_factory=list)


@dataclass
class ReportResult:
    name: str
    path: str
    tier1_ok: bool = False
    tier1_error: str | None = None
    pages: list[PageResult] = field(default_factory=list)
    # Totals (populated in main)
    total_visuals: int = 0
    tier2_passed: int = 0
    tier2_failed: int = 0
    filter_validated: int = 0
    filter_failed: int = 0
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VERBOSE = "--verbose" in sys.argv
TIER1_ONLY = "--tier1-only" in sys.argv

RESET = "\033[0m"
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"


def _ok(text: str = "PASS") -> str:
    return f"{GREEN}{text}{RESET}"


def _fail(text: str = "FAIL") -> str:
    return f"{RED}{text}{RESET}"


def _warn(text: str) -> str:
    return f"{YELLOW}{text}{RESET}"


def print_header(title: str) -> None:
    print(f"\n{'=' * 72}")
    print(f" {BOLD}{title}{RESET}")
    print("=" * 72)


def _shorten(err: str, max_len: int = 200) -> str:
    return err if len(err) <= max_len else err[:max_len] + "…"


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def discover_pbir_reports(root: Path) -> list[tuple[str, Path]]:
    """Return (name, report_path) for every .Report folder under *root*."""
    reports: list[tuple[str, Path]] = []
    if not root.exists():
        return reports
    for sample_dir in sorted(root.iterdir()):
        if not sample_dir.is_dir():
            continue
        for entry in sorted(sample_dir.iterdir()):
            if entry.is_dir() and entry.name.endswith(".Report"):
                definition = entry / "definition"
                if (definition / "version.json").exists():
                    name = sample_dir.name
                    reports.append((name, entry))
    return reports


# ---------------------------------------------------------------------------
# Tier 1: pipeline load (permissive)
# ---------------------------------------------------------------------------

def tier1_load_report(name: str, report_path: Path) -> ReportResult:
    """Load report via PbirStrategy + LocalTransport (permissive models)."""
    result = ReportResult(name=name, path=str(report_path))
    try:
        PbirStrategy, LocalTransport = _import_pipeline()
        parts = LocalTransport().read_parts(str(report_path))
        report = PbirStrategy().deserialize(parts)

        for pwv in report.sections:
            page_id = pwv.page.name
            display_name = pwv.page.displayName or page_id
            page_result = PageResult(
                page_id=page_id,
                display_name=display_name,
                visual_count=len(pwv.visuals),
            )
            result.pages.append(page_result)
            for vc in pwv.visuals:
                vr = VisualResult(
                    page_name=display_name,
                    visual_id=vc.name or "?",
                    tier1_ok=True,
                )
                page_result.visuals.append(vr)

        result.tier1_ok = True
        result.total_visuals = sum(p.visual_count for p in result.pages)

    except Exception as exc:
        result.tier1_ok = False
        result.tier1_error = f"{type(exc).__name__}: {exc}"
        if VERBOSE:
            result.tier1_error += f"\n{traceback.format_exc()}"

    return result


# ---------------------------------------------------------------------------
# Tier 2: strict model validation (generated schemas)
# ---------------------------------------------------------------------------

def tier2_validate_report(result: ReportResult, report_path: Path) -> None:
    """Validate every visual.json and filterConfig with strict generated models."""
    try:
        init_visual_container_for_schema, FilterConfiguration = _import_strict_models()
    except ImportError as exc:
        result.warnings.append(f"Cannot import strict models: {exc}")
        return

    definition = report_path / "definition"
    pages_dir = definition / "pages"
    if not pages_dir.exists():
        result.warnings.append("No definition/pages/ directory found")
        return

    # Build a map from page_id -> PageResult for O(1) lookup
    page_map: dict[str, PageResult] = {p.page_id: p for p in result.pages}

    # Walk every page directory
    for page_dir in sorted(pages_dir.iterdir()):
        if not page_dir.is_dir() or page_dir.name == "pages.json":
            continue
        if (page_dir / "page.json").exists():
            _validate_page_dir(
                page_dir=page_dir,
                page_map=page_map,
                result=result,
                init_visual_container_for_schema=init_visual_container_for_schema,
                FilterConfiguration=FilterConfiguration,
            )


def _validate_page_dir(
    page_dir: Path,
    page_map: dict[str, PageResult],
    result: ReportResult,
    init_visual_container_for_schema,
    FilterConfiguration,
) -> None:
    page_id = page_dir.name

    # Read page.json for display name (fall back to id)
    page_json_path = page_dir / "page.json"
    display_name = page_id
    try:
        page_data = json.loads(page_json_path.read_bytes())
        display_name = page_data.get("displayName") or page_id

        # Validate page-level filterConfig if present
        if "filterConfig" in page_data:
            _validate_filter(
                raw=page_data["filterConfig"],
                context=f"page '{display_name}' filterConfig",
                result=result,
                FilterConfiguration=FilterConfiguration,
            )
    except Exception as exc:
        result.warnings.append(f"page.json parse error ({page_id}): {exc}")

    visuals_dir = page_dir / "visuals"
    if not visuals_dir.exists():
        return

    # Locate / create PageResult for this page
    pr = page_map.get(page_id)
    if pr is None:
        pr = PageResult(page_id=page_id, display_name=display_name)
        page_map[page_id] = pr
        result.pages.append(pr)

    for visual_dir in sorted(visuals_dir.iterdir()):
        if not visual_dir.is_dir():
            continue
        visual_json_path = visual_dir / "visual.json"
        if not visual_json_path.exists():
            continue

        visual_id = visual_dir.name
        vr = _find_or_create_visual(pr, visual_id, display_name)

        # --- Strict VisualContainer parse ---
        try:
            raw = json.loads(visual_json_path.read_bytes())
            vc = init_visual_container_for_schema(raw)
            vr.tier2_ok = True
            result.tier2_passed += 1

            # --- Strict FilterConfiguration parse (from visual filterConfig) ---
            filter_raw = raw.get("filterConfig")
            if filter_raw is not None:
                vr.has_filter = True
                try:
                    FilterConfiguration.model_validate(filter_raw)
                    vr.filter_ok = True
                    result.filter_validated += 1
                except Exception as fexc:
                    vr.filter_ok = False
                    vr.filter_error = f"{type(fexc).__name__}: {fexc}"
                    result.filter_failed += 1
                    if VERBOSE:
                        vr.filter_error += f"\n{traceback.format_exc()}"
        except Exception as exc:
            vr.tier2_ok = False
            vr.tier2_error = f"{type(exc).__name__}: {exc}"
            result.tier2_failed += 1
            if VERBOSE:
                vr.tier2_error += f"\n{traceback.format_exc()}"


def _find_or_create_visual(pr: PageResult, visual_id: str, page_name: str) -> VisualResult:
    for vr in pr.visuals:
        if vr.visual_id == visual_id:
            return vr
    vr = VisualResult(page_name=page_name, visual_id=visual_id)
    pr.visuals.append(vr)
    pr.visual_count = len(pr.visuals)
    return vr


def _validate_filter(
    raw: dict,
    context: str,
    result: ReportResult,
    FilterConfiguration,
) -> None:
    try:
        FilterConfiguration.model_validate(raw)
        result.filter_validated += 1
    except Exception as exc:
        result.filter_failed += 1
        result.warnings.append(
            f"Filter validation failed ({context}): "
            f"{type(exc).__name__}: {_shorten(str(exc))}"
        )


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def print_report_result(result: ReportResult) -> None:
    t1_label = _ok("T1:OK") if result.tier1_ok else _fail("T1:FAIL")
    if TIER1_ONLY:
        label = t1_label
    else:
        t2_any = result.tier2_passed + result.tier2_failed
        if t2_any == 0:
            t2_label = _warn("T2:--")
        elif result.tier2_failed == 0:
            t2_label = _ok(f"T2:{result.tier2_passed}/{t2_any}")
        else:
            t2_label = _fail(f"T2:{result.tier2_passed}/{t2_any}")
        label = f"{t1_label}  {t2_label}"

    print(f"\n[{label}] {BOLD}{result.name}{RESET}")
    print(f"    Path : {result.path}")

    if result.tier1_ok:
        page_count = len(result.pages)
        print(f"    Pages: {page_count}   Visuals: {result.total_visuals}")
    else:
        print(f"    {_fail('Pipeline error')}: {result.tier1_error}")

    if not TIER1_ONLY:
        if result.tier2_failed:
            print(f"    {_fail(f'Strict model failures: {result.tier2_failed}')}")
        if result.filter_validated or result.filter_failed:
            filter_total = result.filter_validated + result.filter_failed
            filter_label = (
                _ok(f"Filters: {result.filter_validated}/{filter_total}")
                if result.filter_failed == 0
                else _fail(f"Filters: {result.filter_validated}/{filter_total}")
            )
            print(f"    {filter_label}")

    if result.warnings:
        for w in result.warnings[:5]:
            print(f"    {_warn('WARN')}: {w}")
        if len(result.warnings) > 5:
            print(f"    … and {len(result.warnings) - 5} more warnings")

    # Per-page breakdown (failures only, unless verbose)
    for pr in result.pages:
        failed_visuals = [v for v in pr.visuals if not v.tier2_ok]
        if not failed_visuals and not VERBOSE:
            continue
        visuals_to_show = pr.visuals if VERBOSE else failed_visuals
        if visuals_to_show:
            status = _ok("OK") if not failed_visuals else _fail("FAIL")
            print(f"\n    [{status}] Page: {pr.display_name!r} ({pr.visual_count} visuals)")
            for vr in visuals_to_show:
                v_ok = _ok("ok") if vr.tier2_ok else _fail("!!")
                print(f"      {v_ok}  visual {vr.visual_id[:16]}")
                if not vr.tier2_ok and vr.tier2_error:
                    for line in _shorten(vr.tier2_error, 300).splitlines():
                        print(f"          {line}")
                if vr.has_filter and not vr.filter_ok and vr.filter_error:
                    print(f"          {_warn('filter')}: {_shorten(vr.filter_error)}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print_header("PBIR Data Model Validation")
    print(f"Samples path : {SAMPLES_PATH}")
    print(f"Verbose      : {VERBOSE}")
    print(f"Tier 1 only  : {TIER1_ONLY}")

    reports = discover_pbir_reports(SAMPLES_PATH)

    if not reports:
        print(f"\n{_warn('No PBIR reports found.')} Check that SAMPLES_PATH exists and contains")
        print(".Report folders with definition/version.json inside.")
        return 1

    print(f"\nDiscovered {len(reports)} report(s): {', '.join(n for n, _ in reports)}")

    all_results: list[ReportResult] = []

    for name, report_path in reports:
        # Tier 1 — full pipeline load (permissive)
        result = tier1_load_report(name, report_path)

        # Tier 2 — strict model validation (walk filesystem directly)
        if not TIER1_ONLY and result.tier1_ok:
            tier2_validate_report(result, report_path)
        elif not TIER1_ONLY and not result.tier1_ok:
            # Still try tier 2 even if tier 1 failed (different error path)
            tier2_validate_report(result, report_path)
            result.total_visuals = sum(len(p.visuals) for p in result.pages)

        print_report_result(result)
        all_results.append(result)

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    print_header("Summary")

    t1_pass = sum(1 for r in all_results if r.tier1_ok)
    t1_fail = len(all_results) - t1_pass
    total_visuals = sum(r.total_visuals for r in all_results)
    t2_pass = sum(r.tier2_passed for r in all_results)
    t2_fail = sum(r.tier2_failed for r in all_results)
    f_pass = sum(r.filter_validated for r in all_results)
    f_fail = sum(r.filter_failed for r in all_results)

    print(f"\n{'Reports':<30} {len(all_results):>5}")
    print(f"{'  Tier 1 pass (pipeline)':<30} {t1_pass:>5}")
    print(f"{'  Tier 1 fail':<30} {t1_fail:>5}")
    print()
    print(f"{'Total visuals':<30} {total_visuals:>5}")

    if not TIER1_ONLY:
        total_t2 = t2_pass + t2_fail
        print(f"{'  Tier 2 pass (strict model)':<30} {t2_pass:>5}  / {total_t2}")
        print(f"{'  Tier 2 fail':<30} {t2_fail:>5}  / {total_t2}")
        total_f = f_pass + f_fail
        print(f"{'  Filter configs pass':<30} {f_pass:>5}  / {total_f}")
        print(f"{'  Filter configs fail':<30} {f_fail:>5}  / {total_f}")

    any_failure = t1_fail > 0 or t2_fail > 0 or f_fail > 0

    if any_failure:
        print(f"\n{_fail('Validation completed with failures.')}")
        return 1
    else:
        print(f"\n{_ok('All validations passed.')}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
