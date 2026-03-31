"""
Validation script for the TMDL parser implementation.

This script validates the TMDL parser against the sample files in:
    samples/tmdl/division-sm/definition/

It tests:
1. Lexer - tokenization of TMDL files
2. Parser - AST generation from tokens
3. Transformer - Pydantic model conversion
4. Loader - Full folder loading orchestration
"""

import sys
import traceback
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from poupytempo.persistence.parsers.tmdl.lexer import TMDLLexer, TokenType
from poupytempo.persistence.parsers.tmdl.parser import TMDLParser, parse_tmdl
from poupytempo.persistence.parsers.tmdl.transformer import TMDLTransformer
from poupytempo.persistence.parsers.tmdl.loader import TMDLFolderLoader
from poupytempo import SemanticModel

SAMPLE_PATH = (
    Path(__file__).parent.parent.parent / "samples" / "tmdl" / "division-sm" / "definition"
)

# SM root for the high-level API (parent of definition/)
SAMPLE_ROOT = SAMPLE_PATH.parent


def print_header(title: str) -> None:
    print("\n" + "=" * 60)
    print(f" {title}")
    print("=" * 60)


def print_result(name: str, success: bool, detail: str = "") -> None:
    status = "\033[92mPASS\033[0m" if success else "\033[91mFAIL\033[0m"
    print(f"  [{status}] {name}")
    if detail and not success:
        for line in detail.split("\n")[:5]:
            print(f"         {line}")


def validate_lexer(file_path: Path) -> tuple[bool, str, list]:
    """Validate the lexer can tokenize a file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        lexer = TMDLLexer(content, str(file_path))
        tokens = list(lexer.tokenize())

        # Basic validation
        if not tokens:
            return False, "No tokens generated", []

        if tokens[-1].type != TokenType.EOF:
            return False, "Missing EOF token", tokens

        return True, f"{len(tokens)} tokens", tokens
    except Exception as e:
        return False, f"{type(e).__name__}: {e}", []


def validate_parser(file_path: Path) -> tuple[bool, str, list]:
    """Validate the parser can parse a file into AST."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        nodes = parse_tmdl(content, str(file_path))

        if not nodes:
            return False, "No AST nodes generated", []

        return True, f"{len(nodes)} top-level nodes", nodes
    except Exception as e:
        return False, f"{type(e).__name__}: {e}\n{traceback.format_exc()}", []


def validate_transformer(file_path: Path, object_type: str) -> tuple[bool, str, object]:
    """Validate the transformer can convert AST to Pydantic models."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        nodes = parse_tmdl(content, str(file_path))
        transformer = TMDLTransformer(str(file_path))

        result = None
        for node in nodes:
            if node.object_type == object_type:
                if object_type == "table":
                    result = transformer.transform_table(node)
                elif object_type == "expression":
                    result = transformer.transform_expression(node)
                elif object_type == "relationship":
                    result = transformer.transform_relationship(node)
                elif object_type == "database":
                    result = transformer.transform_database(node)
                elif object_type == "cultureInfo":
                    result = transformer.transform_culture(node)
                break

        if result is None:
            return False, f"No {object_type} node found", None

        return True, f"Transformed to {type(result).__name__}", result
    except Exception as e:
        return False, f"{type(e).__name__}: {e}\n{traceback.format_exc()}", None


def validate_full_load() -> tuple[bool, str, dict]:
    """Validate full folder loading."""
    try:
        loader = TMDLFolderLoader(str(SAMPLE_PATH))
        result = loader.load()

        model = result.get("model")
        if not model:
            return False, "No model in result", result

        tables = model.tables or []
        relationships = model.relationships or []
        expressions = model.expressions or []

        summary = (
            f"compatibilityLevel={result.get('compatibilityLevel')}, "
            f"{len(tables)} tables, {len(relationships)} relationships, "
            f"{len(expressions)} expressions"
        )

        return True, summary, result
    except Exception as e:
        return False, f"{type(e).__name__}: {e}\n{traceback.format_exc()}", {}


def validate_semantic_model() -> tuple[bool, str, object]:
    """Validate SemanticModel.read()."""
    try:
        sm = SemanticModel.read(str(SAMPLE_ROOT))

        tables = sm.definition.model.tables or []
        relationships = sm.definition.model.relationships or []

        # Validate some tables
        table_names = [t.name for t in tables]

        summary = (
            f"{len(tables)} tables, {len(relationships)} relationships, "
            f"first table: {table_names[0] if table_names else 'N/A'}"
        )

        return True, summary, sm
    except Exception as e:
        return False, f"{type(e).__name__}: {e}\n{traceback.format_exc()}", None


def validate_table_content(sm) -> list[tuple[str, bool, str]]:
    """Validate content of loaded tables."""
    results = []

    tables = sm.definition.model.tables or []
    for table in tables[:10]:  # Check first 10 tables
        issues = []

        # Check required fields
        if not table.name:
            issues.append("missing name")
        if not table.lineageTag:
            issues.append("missing lineageTag")

        # Check partitions
        if not table.partitions:
            issues.append("no partitions")

        # Check columns
        if table.columns:
            for col in table.columns:
                if not col.name:
                    issues.append(f"column missing name")
                if not col.lineageTag:
                    issues.append(f"column {col.name} missing lineageTag")

        success = len(issues) == 0
        detail = ", ".join(issues) if issues else "OK"
        results.append((f"Table: {table.name}", success, detail))

    return results


def validate_expression_content(sm) -> list[tuple[str, bool, str]]:
    """Validate content of loaded expressions."""
    results = []

    expressions = sm.definition.model.expressions or []
    for expr in expressions:
        issues = []

        if not expr.name:
            issues.append("missing name")
        if not expr.expression:
            issues.append("missing expression body")

        success = len(issues) == 0
        detail = (
            f"expression length: {len(str(expr.expression))}"
            if success
            else ", ".join(issues)
        )
        results.append((f"Expression: {expr.name}", success, detail))

    return results


def validate_relationship_content(sm) -> list[tuple[str, bool, str]]:
    """Validate content of loaded relationships."""
    results = []

    relationships = sm.definition.model.relationships or []
    for rel in relationships[:10]:  # Check first 10
        issues = []

        if not rel.name:
            issues.append("missing name")
        if not rel.fromTable:
            issues.append("missing fromTable")
        if not rel.fromColumn:
            issues.append("missing fromColumn")
        if not rel.toTable:
            issues.append("missing toTable")
        if not rel.toColumn:
            issues.append("missing toColumn")

        success = len(issues) == 0
        detail = (
            f"{rel.fromTable}.{rel.fromColumn} -> {rel.toTable}.{rel.toColumn}"
            if success
            else ", ".join(issues)
        )
        results.append((f"Relationship: {rel.name[:20]}...", success, detail))

    return results


def main():
    print_header("TMDL Parser Validation")
    print(f"Sample path: {SAMPLE_PATH}")

    if not SAMPLE_PATH.exists():
        print(f"\033[91mERROR: Sample path does not exist!\033[0m")
        return 1

    total_tests = 0
    passed_tests = 0

    # 1. Validate Lexer
    print_header("1. Lexer Validation")

    test_files = [
        SAMPLE_PATH / "database.tmdl",
        SAMPLE_PATH / "model.tmdl",
        SAMPLE_PATH / "expressions.tmdl",
        SAMPLE_PATH / "relationships.tmdl",
        SAMPLE_PATH / "tables" / "dim_calendar.tmdl",
    ]

    for file_path in test_files:
        if file_path.exists():
            success, detail, _ = validate_lexer(file_path)
            print_result(f"Lexer: {file_path.name}", success, detail)
            total_tests += 1
            if success:
                passed_tests += 1

    # 2. Validate Parser
    print_header("2. Parser Validation")

    for file_path in test_files:
        if file_path.exists():
            success, detail, _ = validate_parser(file_path)
            print_result(f"Parser: {file_path.name}", success, detail)
            total_tests += 1
            if success:
                passed_tests += 1

    # 3. Validate Transformer
    print_header("3. Transformer Validation")

    transformer_tests = [
        (SAMPLE_PATH / "database.tmdl", "database"),
        (SAMPLE_PATH / "expressions.tmdl", "expression"),
        (SAMPLE_PATH / "relationships.tmdl", "relationship"),
        (SAMPLE_PATH / "tables" / "dim_calendar.tmdl", "table"),
        (SAMPLE_PATH / "cultures" / "en-US.tmdl", "cultureInfo"),
    ]

    for file_path, obj_type in transformer_tests:
        if file_path.exists():
            success, detail, _ = validate_transformer(file_path, obj_type)
            print_result(f"Transform {obj_type}: {file_path.name}", success, detail)
            total_tests += 1
            if success:
                passed_tests += 1

    # 4. Validate Full Load
    print_header("4. Full Folder Load Validation")

    success, detail, result = validate_full_load()
    print_result("TMDLFolderLoader.load()", success, detail)
    total_tests += 1
    if success:
        passed_tests += 1

    # 5. Validate SemanticModel Integration
    print_header("5. SemanticModel Integration")

    success, detail, model = validate_semantic_model()
    print_result("SemanticModel.read()", success, detail)
    total_tests += 1
    if success:
        passed_tests += 1

    # 6. Validate Content
    if model:
        print_header("6. Content Validation")

        # Tables
        for name, success, detail in validate_table_content(model):
            print_result(name, success, detail)
            total_tests += 1
            if success:
                passed_tests += 1

        # Expressions
        for name, success, detail in validate_expression_content(model):
            print_result(name, success, detail)
            total_tests += 1
            if success:
                passed_tests += 1

        # Relationships
        for name, success, detail in validate_relationship_content(model):
            print_result(name, success, detail)
            total_tests += 1
            if success:
                passed_tests += 1

    # Summary
    print_header("Summary")
    print(f"  Total tests: {total_tests}")
    print(f"  Passed: {passed_tests}")
    print(f"  Failed: {total_tests - passed_tests}")

    if passed_tests == total_tests:
        print("\n\033[92m  ALL TESTS PASSED!\033[0m")
        return 0
    else:
        print(f"\n\033[91m  {total_tests - passed_tests} TESTS FAILED!\033[0m")
        return 1


if __name__ == "__main__":
    sys.exit(main())
