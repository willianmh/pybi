"""
Validates TMDL round-trip: load -> write -> load.

This script tests that:
1. A TMDL model can be loaded
2. Written back to a new folder
3. Re-loaded and compared with the original

Usage:
    uv run python scripts/validate_tmdl_roundtrip.py
    uv run python scripts/validate_tmdl_roundtrip.py --sample  # Only test sample model
    uv run python scripts/validate_tmdl_roundtrip.py --verbose  # Show detailed output
"""

import argparse
import os
import shutil
import sys
import tempfile
import traceback
from dataclasses import dataclass, field
from pathlib import Path

from poupytempo import SemanticModel
from poupytempo.utils.enums import FabricFormat

# Sample model path (SM root, contains definition/ subfolder)
SAMPLE_MODEL_PATH = (
    Path(__file__).parent.parent.parent / "samples" / "tmdl" / "division-sm"
)

# Production workspace path (optional)
DASHBOARDS_PATH = "C:\\Users\\haw4ca\\Documents\\code\\pbi_workspace"


@dataclass
class ValidationResult:
    """Result of a round-trip validation."""

    name: str
    path: str
    success: bool
    original_tables: int = 0
    original_columns: int = 0
    original_measures: int = 0
    original_relationships: int = 0
    original_expressions: int = 0
    reloaded_tables: int = 0
    reloaded_columns: int = 0
    reloaded_measures: int = 0
    reloaded_relationships: int = 0
    reloaded_expressions: int = 0
    error: str | None = None
    warnings: list[str] = field(default_factory=list)


def count_model_elements(sm: SemanticModel) -> dict[str, int]:
    """Count elements in a semantic model."""
    model = sm.definition.model
    tables = len(model.tables) if model.tables else 0
    relationships = len(model.relationships) if model.relationships else 0
    expressions = len(model.expressions) if model.expressions else 0

    columns = 0
    measures = 0
    for table in model.tables or []:
        columns += len(table.columns) if table.columns else 0
        measures += len(table.measures) if table.measures else 0

    return {
        "tables": tables,
        "columns": columns,
        "measures": measures,
        "relationships": relationships,
        "expressions": expressions,
    }


def compare_models(original: SemanticModel, reloaded: SemanticModel) -> list[str]:
    """Compare two semantic models and return differences."""
    warnings: list[str] = []

    orig_counts = count_model_elements(original)
    reload_counts = count_model_elements(reloaded)

    for key in orig_counts:
        if orig_counts[key] != reload_counts[key]:
            warnings.append(
                f"{key}: original={orig_counts[key]}, reloaded={reload_counts[key]}"
            )

    # Compare table names
    orig_table_names = {t.name for t in (original.definition.model.tables or [])}
    reload_table_names = {t.name for t in (reloaded.definition.model.tables or [])}

    missing_tables = orig_table_names - reload_table_names
    extra_tables = reload_table_names - orig_table_names

    if missing_tables:
        warnings.append(f"Missing tables: {missing_tables}")
    if extra_tables:
        warnings.append(f"Extra tables: {extra_tables}")

    # Compare relationship names
    orig_rel_names = {r.name for r in (original.definition.model.relationships or [])}
    reload_rel_names = {r.name for r in (reloaded.definition.model.relationships or [])}

    missing_rels = orig_rel_names - reload_rel_names
    extra_rels = reload_rel_names - orig_rel_names

    if missing_rels:
        warnings.append(f"Missing relationships: {missing_rels}")
    if extra_rels:
        warnings.append(f"Extra relationships: {extra_rels}")

    return warnings


def validate_roundtrip(
    name: str, sm_root_path: str, verbose: bool = False
) -> ValidationResult:
    """Validate round-trip for a single TMDL model."""
    result = ValidationResult(name=name, path=sm_root_path, success=False)

    temp_dir = None
    try:
        # Step 1: Load original model
        if verbose:
            print(f"  Loading original: {sm_root_path}")
        original = SemanticModel.read(sm_root_path)

        orig_counts = count_model_elements(original)
        result.original_tables = orig_counts["tables"]
        result.original_columns = orig_counts["columns"]
        result.original_measures = orig_counts["measures"]
        result.original_relationships = orig_counts["relationships"]
        result.original_expressions = orig_counts["expressions"]

        # Step 2: Write to temporary folder
        temp_dir = tempfile.mkdtemp(prefix="tmdl_roundtrip_")
        output_path = os.path.join(temp_dir, "SM")
        if verbose:
            print(f"  Writing to: {output_path}")
        original.write(output_path, format=FabricFormat.TMDL)

        # Step 3: Reload from written folder
        if verbose:
            print(f"  Reloading from: {output_path}")
        reloaded = SemanticModel.read(output_path)

        reload_counts = count_model_elements(reloaded)
        result.reloaded_tables = reload_counts["tables"]
        result.reloaded_columns = reload_counts["columns"]
        result.reloaded_measures = reload_counts["measures"]
        result.reloaded_relationships = reload_counts["relationships"]
        result.reloaded_expressions = reload_counts["expressions"]

        # Step 4: Compare models
        result.warnings = compare_models(original, reloaded)

        # Success if no critical differences
        result.success = (
            result.original_tables == result.reloaded_tables
            and result.original_relationships == result.reloaded_relationships
        )

    except Exception as e:
        result.error = f"{type(e).__name__}: {str(e)}"
        if verbose:
            result.error += f"\n{traceback.format_exc()}"

    finally:
        # Clean up temp directory
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except Exception:
                pass

    return result


def discover_tmdl_models(workspace_path: str) -> list[tuple[str, str]]:
    """Discover TMDL models in the workspace."""
    models = []

    if not os.path.exists(workspace_path):
        return models

    for folder in os.listdir(workspace_path):
        folder_path = os.path.join(workspace_path, folder)
        if not os.path.isdir(folder_path):
            continue

        dashboards_folder = os.path.join(folder_path, "dashboards")
        if not os.path.exists(dashboards_folder):
            continue

        for subfolder in os.listdir(dashboards_folder):
            subfolder_path = os.path.join(dashboards_folder, subfolder)
            if not os.path.isdir(subfolder_path):
                continue

            if not (
                subfolder_path.endswith(".Dataset")
                or subfolder_path.endswith(".SemanticModel")
            ):
                continue

            name = subfolder.split(".")[0]

            # Only TMDL models (definition folder present)
            definition_path = os.path.join(subfolder_path, "definition")
            if os.path.exists(definition_path):
                models.append((name, subfolder_path))

    return models


def print_header(title: str) -> None:
    """Print a section header."""
    print("\n" + "=" * 70)
    print(f" {title}")
    print("=" * 70)


def print_result(result: ValidationResult, verbose: bool = False) -> None:
    """Print validation result."""
    status = "\033[92mPASS\033[0m" if result.success else "\033[91mFAIL\033[0m"
    print(f"\n[{status}] {result.name}")
    print(f"    Path: {result.path}")

    if result.success or verbose:
        print(
            f"    Original:  Tables={result.original_tables}, Cols={result.original_columns}, "
            f"Measures={result.original_measures}, Rels={result.original_relationships}, "
            f"Exprs={result.original_expressions}"
        )
        print(
            f"    Reloaded:  Tables={result.reloaded_tables}, Cols={result.reloaded_columns}, "
            f"Measures={result.reloaded_measures}, Rels={result.reloaded_relationships}, "
            f"Exprs={result.reloaded_expressions}"
        )

    if result.error:
        print(f"    Error: {result.error}")

    if result.warnings:
        for warning in result.warnings[:5]:
            print(f"    Warning: {warning}")
        if len(result.warnings) > 5:
            print(f"    ... and {len(result.warnings) - 5} more warnings")


def main():
    parser = argparse.ArgumentParser(description="Validate TMDL round-trip")
    parser.add_argument("--sample", action="store_true", help="Only test sample model")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument(
        "--path", type=str, help="Path to specific TMDL definition folder"
    )
    args = parser.parse_args()

    print_header("TMDL Round-Trip Validation")

    results: list[ValidationResult] = []

    # Test specific path if provided
    if args.path:
        path = Path(args.path)
        # If user pointed at the definition/ folder, go up one level
        if path.name == "definition":
            path = path.parent
        name = path.name
        print(f"\nValidating: {path}")
        result = validate_roundtrip(name, str(path), args.verbose)
        results.append(result)
        print_result(result, args.verbose)

    # Test sample model
    elif args.sample or not os.path.exists(DASHBOARDS_PATH):
        if SAMPLE_MODEL_PATH.exists():
            print(f"\nValidating sample model: {SAMPLE_MODEL_PATH}")
            result = validate_roundtrip(
                "division-sm", str(SAMPLE_MODEL_PATH), args.verbose
            )
            results.append(result)
            print_result(result, args.verbose)
        else:
            print(f"\nSample model not found at: {SAMPLE_MODEL_PATH}")
            return 1

    # Test all production models
    else:
        models = discover_tmdl_models(DASHBOARDS_PATH)
        print(f"\nDiscovered {len(models)} TMDL model(s)")

        for name, path in models:
            print(f"\nValidating: {name}")
            result = validate_roundtrip(name, path, args.verbose)
            results.append(result)
            print_result(result, args.verbose)

    # Summary
    print_header("Summary")

    passed = sum(1 for r in results if r.success)
    failed = len(results) - passed

    print(f"\nTotal: {len(results)} models validated")
    print(f"  Passed: {passed}")
    print(f"  Failed: {failed}")

    # Element totals
    total_tables = sum(r.original_tables for r in results if r.success)
    total_columns = sum(r.original_columns for r in results if r.success)
    total_measures = sum(r.original_measures for r in results if r.success)
    total_relationships = sum(r.original_relationships for r in results if r.success)

    if results:
        print(f"\nTotal elements round-tripped:")
        print(f"  Tables: {total_tables}")
        print(f"  Columns: {total_columns}")
        print(f"  Measures: {total_measures}")
        print(f"  Relationships: {total_relationships}")

    if failed > 0:
        print(f"\n\033[91m{failed} model(s) failed validation!\033[0m")
        return 1
    else:
        print(f"\n\033[92mAll {passed} model(s) validated successfully!\033[0m")
        return 0


if __name__ == "__main__":
    sys.exit(main())
