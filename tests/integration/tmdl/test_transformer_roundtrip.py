"""Integration tests: full TMDL pipeline (text → AST → Pydantic models) on real samples.

Uses ``TMDLPartsLoader`` to load real sample directories through the complete
parser + transformer pipeline.  Tests marked ``xfail`` expose known bugs in the
transformer layer.
"""

from pathlib import Path

import pytest

from pybi.serialization.parsers.tmdl.loader import TMDLPartsLoader

# ---------------------------------------------------------------------------
# Paths to sample semantic model definition directories
# ---------------------------------------------------------------------------

_SAMPLES_ROOT = Path("samples/pbir/11.25")

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
# Helpers
# ---------------------------------------------------------------------------


def _load_tmdl_files(sem_model_dir: Path) -> dict[str, str]:
    """Build the {relative_path: text} dict that TMDLPartsLoader expects."""
    definition_dir = sem_model_dir / "definition"
    files: dict[str, str] = {}
    for tmdl_path in sorted(definition_dir.rglob("*.tmdl")):
        rel = tmdl_path.relative_to(definition_dir).as_posix()
        files[rel] = tmdl_path.read_text(encoding="utf-8")
    return files


def _load_sample(name: str):
    """Load a sample through the full pipeline and return the result dict."""
    sem_dir = _SAMPLE_DIRS[name]
    files = _load_tmdl_files(sem_dir)
    return TMDLPartsLoader(files).load()


# ---------------------------------------------------------------------------
# TestLoaderOnAllSamples — parametrized smoke tests
# ---------------------------------------------------------------------------


class TestLoaderOnAllSamples:
    @pytest.fixture(
        params=sorted(_SAMPLE_DIRS.keys()),
        ids=lambda k: k,
    )
    def sample_name(self, request) -> str:
        return request.param

    @pytest.fixture
    def loaded(self, sample_name):
        return _load_sample(sample_name)

    def test_load_does_not_crash(self, loaded):
        """TMDLPartsLoader.load() completes without error."""
        assert loaded is not None

    def test_result_has_compatibility_level(self, loaded):
        assert "compatibilityLevel" in loaded
        assert isinstance(loaded["compatibilityLevel"], int)

    def test_result_has_model(self, loaded):
        from pybi.semanticmodel.definition import Model

        assert "model" in loaded
        assert isinstance(loaded["model"], Model)

    def test_model_has_tables(self, loaded):
        model = loaded["model"]
        assert model.tables is not None
        assert len(model.tables) >= 1

    def test_model_has_cultures(self, loaded):
        model = loaded["model"]
        assert model.cultures is not None
        assert len(model.cultures) >= 1

    def test_all_tables_have_partitions(self, loaded):
        """Every table must have at least one partition."""
        model = loaded["model"]
        for table in model.tables:
            assert table.partitions is not None and len(table.partitions) >= 1, (
                f"Table {table.name!r} has no partitions"
            )


# ---------------------------------------------------------------------------
# TestAISample — targeted assertions on the AI sample
# ---------------------------------------------------------------------------


class TestAISample:
    @pytest.fixture(scope="class")
    def loaded(self):
        return _load_sample("ai")

    @pytest.fixture(scope="class")
    def model(self, loaded):
        return loaded["model"]

    def test_compatibility_level(self, loaded):
        assert loaded["compatibilityLevel"] == 1567

    def test_table_count(self, model):
        """AI sample has 18 tables (including LocalDateTable_ templates)."""
        assert len(model.tables) == 18

    def test_relationship_count(self, model):
        assert model.relationships is not None
        assert len(model.relationships) == 17

    def test_expression_count(self, model):
        assert len(model.expressions) >= 1

    def test_accounts_table_exists(self, model):
        t = next((t for t in model.tables if t.name == "Accounts"), None)
        assert t is not None

    def test_accounts_column_count(self, model):
        t = next(t for t in model.tables if t.name == "Accounts")
        assert t.columns is not None
        assert len(t.columns) >= 15

    def test_accounts_hierarchy(self, model):
        t = next(t for t in model.tables if t.name == "Accounts")
        assert t.hierarchies is not None
        assert len(t.hierarchies) == 1
        hier = t.hierarchies[0]
        assert hier["name"] == "Location Hierarchy"
        # Levels stored under singular key (not in CHILDREN_NAMING_MAP)
        assert "level" in hier

    def test_accounts_calculated_column_expression(self, model):
        """'Industry Lookup' calculated column should have its LOOKUPVALUE expression."""
        t = next(t for t in model.tables if t.name == "Accounts")
        col = next((c for c in t.columns if c.name == "Industry Lookup"), None)
        assert col is not None
        assert col.expression is not None
        expr_str = (
            col.expression if isinstance(col.expression, str) else col.expression[0]
        )
        assert "LOOKUPVALUE" in expr_str

    def test_opportunities_measures(self, model):
        t = next(t for t in model.tables if t.name == "Opportunities")
        assert t.measures is not None
        assert len(t.measures) >= 5
        names = {m.name for m in t.measures}
        assert "Revenue Won" in names
        assert "Revenue In Pipeline" in names

    def test_opportunities_measure_expression_content(self, model):
        """'Revenue Won' measure expression contains CALCULATE."""
        t = next(t for t in model.tables if t.name == "Opportunities")
        m = next(m for m in t.measures if m.name == "Revenue Won")
        expr = (
            m.expression if isinstance(m.expression, str) else "\n".join(m.expression)
        )
        assert "CALCULATE" in expr

    def test_opportunities_column_variation(self, model):
        """'Opportunity Created On' column should have a variation."""
        t = next(t for t in model.tables if t.name == "Opportunities")
        col = next((c for c in t.columns if c.name == "Opportunity Created On"), None)
        assert col is not None
        assert col.variations is not None
        assert len(col.variations) == 1
        assert col.variations[0].name == "Variation"

    def test_opportunities_calculated_columns(self, model):
        """'Weeks Open' and 'Days Remaining In Pipeline' should have expressions."""
        t = next(t for t in model.tables if t.name == "Opportunities")
        calc_cols = {c.name: c for c in t.columns if c.expression is not None}
        assert "Weeks Open" in calc_cols
        assert "Days Remaining In Pipeline" in calc_cols

    def test_relationship_column_refs_parsed(self, model):
        """Relationship fromTable/fromColumn/toTable/toColumn are populated."""
        for rel in model.relationships:
            assert rel.fromTable, f"Empty fromTable in relationship {rel.name}"
            assert rel.fromColumn, f"Empty fromColumn in relationship {rel.name}"
            assert rel.toTable, f"Empty toTable in relationship {rel.name}"
            assert rel.toColumn, f"Empty toColumn in relationship {rel.name}"

    def test_inactive_relationships(self, model):
        """At least 2 relationships have isActive=false."""
        inactive = [
            r
            for r in model.relationships
            if r.isActive is False or r.isActive == "false"
        ]
        assert len(inactive) >= 2


# ---------------------------------------------------------------------------
# TestHumanResourcesSample
# ---------------------------------------------------------------------------


class TestHumanResourcesSample:
    @pytest.fixture(scope="class")
    def loaded(self):
        return _load_sample("human-resources")

    @pytest.fixture(scope="class")
    def model(self, loaded):
        return loaded["model"]

    def test_table_count(self, model):
        assert model.tables is not None
        assert len(model.tables) >= 10

    def test_relationship_count(self, model):
        assert model.relationships is not None
        assert len(model.relationships) >= 5

    def test_employee_table_has_columns(self, model):
        t = next((t for t in model.tables if t.name == "Employee"), None)
        assert t is not None
        assert t.columns is not None
        assert len(t.columns) >= 5


# ---------------------------------------------------------------------------
# TestRevenueOpportunitiesSample
# ---------------------------------------------------------------------------


class TestRevenueOpportunitiesSample:
    @pytest.fixture(scope="class")
    def loaded(self):
        return _load_sample("revenue-opportunities")

    @pytest.fixture(scope="class")
    def model(self, loaded):
        return loaded["model"]

    def test_table_count(self, model):
        assert model.tables is not None
        assert len(model.tables) >= 4

    def test_accounts_table(self, model):
        t = next((t for t in model.tables if t.name == "Accounts"), None)
        assert t is not None
        assert t.columns is not None

    def test_sales_table_has_measures(self, model):
        t = next((t for t in model.tables if t.name == "Sales"), None)
        assert t is not None
        assert t.measures is not None
        assert len(t.measures) >= 1
