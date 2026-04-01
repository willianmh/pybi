"""Integration tests for ``SemanticModel.read()`` against real sample directories.

Validates the highest-level entry point: disk → Parts → TmdlStrategy → SemanticModel.
Tests marked ``xfail`` expose known transformer bugs that surface through this path.
"""

from pathlib import Path

import pytest

from pybi.semanticmodel.semanticmodel import SemanticModel

# ---------------------------------------------------------------------------
# Sample directory paths (each points to the .SemanticModel folder)
# ---------------------------------------------------------------------------

_SAMPLES_ROOT = Path("../pbi-samples/pbi/pbir/11.25")

pytestmark = pytest.mark.skipif(
    not Path("../pbi-samples").exists(),
    reason="pbi-samples repository not available; clone https://github.com/willianmh/pbi-samples",
)

_SAMPLE_DIRS: dict[str, Path] = {
    "ai": _SAMPLES_ROOT / "ai" / "Artificial Intelligence Sample.SemanticModel",
    "human-resources": _SAMPLES_ROOT
    / "human-resources"
    / "Human Resources Sample PBIX.SemanticModel",
    "covid-19-us": _SAMPLES_ROOT
    / "covid-19-us"
    / "COVID-19 US Tracking Sample.SemanticModel",
    "covid-bakeoff": _SAMPLES_ROOT / "covid-bakeoff" / "COVID Bakeoff.SemanticModel",
    "life-expectancy": _SAMPLES_ROOT
    / "life-expectancy"
    / "Life expectancy v202009.SemanticModel",
    "revenue-opportunities": _SAMPLES_ROOT
    / "revenue-opportunities"
    / "Revenue Opportunities.SemanticModel",
}


# ---------------------------------------------------------------------------
# TestReadOnAllSamples — parametrized smoke tests
# ---------------------------------------------------------------------------


class TestReadOnAllSamples:
    @pytest.fixture(
        params=sorted(_SAMPLE_DIRS.keys()),
        ids=lambda k: k,
    )
    def sample_name(self, request) -> str:
        return request.param

    @pytest.fixture
    def sm(self, sample_name) -> SemanticModel:
        return SemanticModel.read(str(_SAMPLE_DIRS[sample_name]))

    def test_read_does_not_crash(self, sm):
        """SemanticModel.read() completes without error."""
        assert sm is not None

    def test_has_definition(self, sm):
        assert sm.definition is not None

    def test_has_model(self, sm):
        assert sm.definition.model is not None

    def test_has_tables(self, sm):
        model = sm.definition.model
        assert model.tables is not None
        assert len(model.tables) >= 1

    def test_has_cultures(self, sm):
        model = sm.definition.model
        assert model.cultures is not None
        assert len(model.cultures) >= 1

    def test_all_tables_have_names(self, sm):
        for table in sm.definition.model.tables:
            assert table.name, f"Table with empty name found"

    def test_all_tables_have_partitions(self, sm):
        for table in sm.definition.model.tables:
            assert table.partitions and len(table.partitions) >= 1, (
                f"Table {table.name!r} has no partitions"
            )


# ---------------------------------------------------------------------------
# TestReadAISample — targeted assertions
# ---------------------------------------------------------------------------


class TestReadAISample:
    @pytest.fixture(scope="class")
    def sm(self) -> SemanticModel:
        return SemanticModel.read(str(_SAMPLE_DIRS["ai"]))

    @pytest.fixture(scope="class")
    def model(self, sm):
        return sm.definition.model

    def test_compatibility_level(self, sm):
        assert sm.definition.compatibilityLevel == 1567

    def test_table_count(self, model):
        assert len(model.tables) == 18

    def test_relationship_count(self, model):
        assert model.relationships is not None
        assert len(model.relationships) == 17

    def test_expression_count(self, model):
        assert len(model.expressions) >= 1

    def test_culture(self, model):
        assert model.cultures is not None
        names = [c.name for c in model.cultures]
        assert "en-US" in names

    def test_calculated_column_expression_preserved(self, model):
        """'Industry Lookup' in Accounts table should have LOOKUPVALUE expression."""
        t = next(t for t in model.tables if t.name == "Accounts")
        col = next((c for c in t.columns if c.name == "Industry Lookup"), None)
        assert col is not None
        assert col.expression is not None
        expr_str = (
            col.expression if isinstance(col.expression, str) else col.expression[0]
        )
        assert "LOOKUPVALUE" in expr_str

    def test_column_variation_preserved(self, model):
        """'Opportunity Created On' column should have a variation."""
        t = next(t for t in model.tables if t.name == "Opportunities")
        col = next((c for c in t.columns if c.name == "Opportunity Created On"), None)
        assert col is not None
        assert col.variations is not None
        assert len(col.variations) == 1

    def test_measure_expressions_not_empty(self, model):
        """All measures across all tables should have non-empty expressions."""
        for table in model.tables:
            if not table.measures:
                continue
            for m in table.measures:
                assert m.expression, (
                    f"Measure {m.name!r} in table {table.name!r} has empty expression"
                )

    def test_partition_sources_have_type(self, model):
        """All partition sources should have a type set."""
        for table in model.tables:
            for p in table.partitions:
                assert p.source is not None
                assert p.source.type is not None, (
                    f"Partition {p.name!r} in table {table.name!r} has no source type"
                )


# ---------------------------------------------------------------------------
# TestReadHumanResourcesSample
# ---------------------------------------------------------------------------


class TestReadHumanResourcesSample:
    @pytest.fixture(scope="class")
    def sm(self) -> SemanticModel:
        return SemanticModel.read(str(_SAMPLE_DIRS["human-resources"]))

    def test_table_count(self, sm):
        model = sm.definition.model
        assert model.tables is not None
        assert len(model.tables) >= 10

    def test_relationship_count(self, sm):
        model = sm.definition.model
        assert model.relationships is not None
        assert len(model.relationships) >= 5

    def test_employee_table(self, sm):
        model = sm.definition.model
        t = next((t for t in model.tables if t.name == "Employee"), None)
        assert t is not None
        assert t.columns is not None
        assert len(t.columns) >= 5
