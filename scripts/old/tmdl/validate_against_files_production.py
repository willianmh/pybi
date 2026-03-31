"""
Validates the TMDL parser against real production files.

This script discovers Semantic Models in the workspace folder and validates:
1. TMDL files (definition folder) - parses and validates structure
2. JSON files (model.bim) - loads and validates for comparison

Usage:
    uv run python scripts/validate_against_files.py
"""

import os
import sys
import traceback
from pathlib import Path
from dataclasses import dataclass, field

from poupytempo import SemanticModel
from poupytempo.semanticmodel.models import SemanticModelDefinition
from poupytempo.utils.utils import read_json

DASHBOARDS_PATH = "C:\\Users\\haw4ca\\Documents\\code\\pbi_workspace"


@dataclass
class ValidationResult:
    """Result of validating a semantic model."""

    name: str
    path: str
    format: str  # "tmdl" or "json"
    success: bool
    tables: int = 0
    columns: int = 0
    measures: int = 0
    relationships: int = 0
    expressions: int = 0
    error: str | None = None
    warnings: list[str] = field(default_factory=list)


def print_header(title: str) -> None:
    """Print a section header."""
    print("\n" + "=" * 70)
    print(f" {title}")
    print("=" * 70)


def print_result(result: ValidationResult) -> None:
    """Print validation result."""
    status = "\033[92mPASS\033[0m" if result.success else "\033[91mFAIL\033[0m"
    print(f"\n[{status}] {result.name} ({result.format})")
    print(f"    Path: {result.path}")

    if result.success:
        print(
            f"    Tables: {result.tables}, Columns: {result.columns}, Measures: {result.measures}"
        )
        print(
            f"    Relationships: {result.relationships}, Expressions: {result.expressions}"
        )
    else:
        print(f"    Error: {result.error}")

    if result.warnings:
        for warning in result.warnings[:5]:
            print(f"    Warning: {warning}")
        if len(result.warnings) > 5:
            print(f"    ... and {len(result.warnings) - 5} more warnings")


def validate_tmdl_model(name: str, sm_root_path: str) -> ValidationResult:
    """Validate a TMDL definition folder."""
    result = ValidationResult(
        name=name, path=sm_root_path, format="tmdl", success=False
    )

    try:
        # Load the model
        sm = SemanticModel.read(sm_root_path)
        model = sm.definition.model

        # Count elements
        result.tables = len(model.tables) if model.tables else 0
        result.relationships = (
            len(model.relationships) if model.relationships else 0
        )
        result.expressions = (
            len(model.expressions) if model.expressions else 0
        )

        # Count columns and measures
        for table in model.tables or []:
            result.columns += len(table.columns) if table.columns else 0
            result.measures += len(table.measures) if table.measures else 0

        # Validate content
        for table in model.tables or []:
            if not table.name:
                result.warnings.append(f"Table missing name")
            if not table.lineageTag:
                result.warnings.append(f"Table '{table.name}' missing lineageTag")
            if not table.partitions:
                result.warnings.append(f"Table '{table.name}' has no partitions")

            for col in table.columns or []:
                if not col.name:
                    result.warnings.append(f"Column in '{table.name}' missing name")
                if not col.lineageTag:
                    result.warnings.append(
                        f"Column '{col.name}' in '{table.name}' missing lineageTag"
                    )

            for measure in table.measures or []:
                if not measure.name:
                    result.warnings.append(f"Measure in '{table.name}' missing name")
                if not measure.expression:
                    result.warnings.append(
                        f"Measure '{measure.name}' in '{table.name}' missing expression"
                    )

        for rel in model.relationships or []:
            if not rel.name:
                result.warnings.append(f"Relationship missing name")
            if not rel.fromTable or not rel.fromColumn:
                result.warnings.append(
                    f"Relationship '{rel.name}' missing fromTable/fromColumn"
                )
            if not rel.toTable or not rel.toColumn:
                result.warnings.append(
                    f"Relationship '{rel.name}' missing toTable/toColumn"
                )

        result.success = True

    except Exception as e:
        result.error = f"{type(e).__name__}: {str(e)}"
        # Include traceback for debugging
        if "--verbose" in sys.argv:
            result.error += f"\n{traceback.format_exc()}"

    return result


def validate_json_model(name: str, json_path: str) -> ValidationResult:
    """Validate a JSON model.bim file."""
    result = ValidationResult(name=name, path=json_path, format="json", success=False)

    try:
        # Load JSON
        json_data = read_json(json_path)

        # Load as SemanticModelDefinition (legacy direct-construction path)
        sm_def = SemanticModelDefinition(**json_data)

        # Count elements
        result.tables = len(sm_def.model.tables) if sm_def.model.tables else 0
        result.relationships = (
            len(sm_def.model.relationships) if sm_def.model.relationships else 0
        )
        result.expressions = (
            len(sm_def.model.expressions) if sm_def.model.expressions else 0
        )

        # Count columns and measures
        for table in sm_def.model.tables or []:
            result.columns += len(table.columns) if table.columns else 0
            result.measures += len(table.measures) if table.measures else 0

        result.success = True

    except Exception as e:
        result.error = f"{type(e).__name__}: {str(e)}"
        if "--verbose" in sys.argv:
            result.error += f"\n{traceback.format_exc()}"

    return result


def discover_semantic_models(workspace_path: str) -> list[tuple[str, str, str]]:
    """
    Discover semantic models in the workspace.

    Returns:
        List of (name, path, format) tuples where format is "tmdl" or "json"
    """
    models = []

    if not os.path.exists(workspace_path):
        print(f"Workspace path does not exist: {workspace_path}")
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

            # Check for TMDL definition folder
            definition_path = os.path.join(subfolder_path, "definition")
            if os.path.exists(definition_path):
                models.append((name, subfolder_path, "tmdl"))
                continue

            # Check for JSON model.bim
            json_path = os.path.join(subfolder_path, "model.bim")
            if os.path.exists(json_path):
                models.append((name, json_path, "json"))

    return models


def main():
    print_header("Semantic Model Validation")
    print(f"Workspace: {DASHBOARDS_PATH}")

    # Discover models
    models = discover_semantic_models(DASHBOARDS_PATH)

    if not models:
        print("\nNo semantic models found in workspace.")
        print(
            "Make sure the workspace path is correct and contains .Dataset or .SemanticModel folders."
        )
        return 1

    print(f"\nDiscovered {len(models)} semantic model(s)")

    # Separate by format
    tmdl_models = [(n, p) for n, p, f in models if f == "tmdl"]
    json_models = [(n, p) for n, p, f in models if f == "json"]

    print(f"  - TMDL format: {len(tmdl_models)}")
    print(f"  - JSON format: {len(json_models)}")

    results: list[ValidationResult] = []

    # Validate TMDL models
    if tmdl_models:
        print_header(f"Validating TMDL Models ({len(tmdl_models)})")
        for name, path in tmdl_models:
            result = validate_tmdl_model(name, path)
            results.append(result)
            print_result(result)

    # Validate JSON models
    if json_models:
        print_header(f"Validating JSON Models ({len(json_models)})")
        for name, path in json_models:
            result = validate_json_model(name, path)
            results.append(result)
            print_result(result)

    # Summary
    print_header("Summary")

    passed = sum(1 for r in results if r.success)
    failed = len(results) - passed

    tmdl_passed = sum(1 for r in results if r.success and r.format == "tmdl")
    tmdl_failed = sum(1 for r in results if not r.success and r.format == "tmdl")
    json_passed = sum(1 for r in results if r.success and r.format == "json")
    json_failed = sum(1 for r in results if not r.success and r.format == "json")

    print(f"\nTotal: {len(results)} models validated")
    print(f"  TMDL: {tmdl_passed} passed, {tmdl_failed} failed")
    print(f"  JSON: {json_passed} passed, {json_failed} failed")

    total_tables = sum(r.tables for r in results if r.success)
    total_columns = sum(r.columns for r in results if r.success)
    total_measures = sum(r.measures for r in results if r.success)
    total_relationships = sum(r.relationships for r in results if r.success)

    print(f"\nTotal elements loaded:")
    print(f"  Tables: {total_tables}")
    print(f"  Columns: {total_columns}")
    print(f"  Measures: {total_measures}")
    print(f"  Relationships: {total_relationships}")

    if failed > 0:
        print(f"\n\033[91m{failed} model(s) failed validation!\033[0m")
        return 1
    else:
        print(f"\n\033[92mAll {passed} models validated successfully!\033[0m")
        return 0


if __name__ == "__main__":
    sys.exit(main())
