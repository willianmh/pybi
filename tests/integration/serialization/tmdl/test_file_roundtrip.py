from pathlib import Path

import pytest

from pybi.serialization.parsers.tmdl.parser import ObjectDeclaration, parse_tmdl
from pybi.serialization.parsers.tmdl.transformer import TMDLTransformer
from pybi.serialization.parsers.tmdl.writer import TMDLWriter


# Fixture root: resolve relative to this file so cwd doesn't matter.
_FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _parse(text: str, path: Path) -> list[ObjectDeclaration]:
    return parse_tmdl(text, file_path=str(path))


class TestTableFileRoundTrip:
    """Round trip each fixture table file: text → Table → text.

    To add a new case: drop a *.tmdl file into
        tests/integration/tmdl/fixtures/tables/
    No code changes required.
    """

    @pytest.fixture(
        params=sorted((_FIXTURES_DIR / "tables").glob("*.tmdl")),
        ids=lambda p: p.stem,
    )
    def fixture_path(self, request) -> Path:
        return request.param

    def test_text_round_trip(self, fixture_path: Path) -> None:
        original = _read(fixture_path)
        nodes = _parse(original, fixture_path)

        assert len(nodes) == 1, (
            f"{fixture_path.name}: expected exactly one top-level node, "
            f"got {len(nodes)}"
        )

        table = TMDLTransformer().transform_table(nodes[0])
        result = TMDLWriter().write_table(table)

        assert result == original, (
            f"Round trip produced different output for {fixture_path.name}.\n"
            f"--- expected (fixture) ---\n{original}\n"
            f"+++ actual (writer) ---\n{result}"
        )


class TestExpressionFileRoundTrip:
    """Round trip each fixture expression file: text → Expression(s) → text.

    To add a new case: drop a *.tmdl file into
        tests/integration/serialization/tmdl/fixtures/expressions/
    """

    @pytest.fixture(
        params=sorted((_FIXTURES_DIR / "expressions").glob("*.tmdl")),
        ids=lambda p: p.stem,
    )
    def fixture_path(self, request) -> Path:
        return request.param

    def test_text_round_trip(self, fixture_path: Path) -> None:
        original = _read(fixture_path)
        nodes = _parse(original, fixture_path)

        assert len(nodes) >= 1, (
            f"{fixture_path.name}: expected at least one top-level node, "
            f"got {len(nodes)}"
        )

        transformer = TMDLTransformer()
        expressions = [transformer.transform_expression(n) for n in nodes]
        result = TMDLWriter().write_expressions(expressions)

        assert result == original, (
            f"Round trip produced different output for {fixture_path.name}.\n"
            f"--- expected (fixture) ---\n{original}\n"
            f"+++ actual (writer) ---\n{result}"
        )


class TestRoleFileRoundTrip:
    """Round trip each fixture role file: text → Role → text.

    To add a new case: drop a *.tmdl file into
        tests/integration/serialization/tmdl/fixtures/roles/
    """

    @pytest.fixture(
        params=sorted((_FIXTURES_DIR / "roles").glob("*.tmdl")),
        ids=lambda p: p.stem,
    )
    def fixture_path(self, request) -> Path:
        return request.param

    def test_text_round_trip(self, fixture_path: Path) -> None:
        original = _read(fixture_path)
        nodes = _parse(original, fixture_path)

        assert len(nodes) == 1, (
            f"{fixture_path.name}: expected exactly one top-level node, "
            f"got {len(nodes)}"
        )

        role = TMDLTransformer().transform_role(nodes[0])
        result = TMDLWriter().write_role(role)

        assert result == original, (
            f"Round trip produced different output for {fixture_path.name}.\n"
            f"--- expected (fixture) ---\n{original}\n"
            f"+++ actual (writer) ---\n{result}"
        )
