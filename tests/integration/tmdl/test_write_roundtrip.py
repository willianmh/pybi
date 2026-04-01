"""Integration tests for the TMDL writer via read → write → read roundtrip.

Validates that ``SemanticModel.write()`` produces TMDL files that can be
read back and yield semantically equivalent models.
"""

from pathlib import Path
import tempfile

import pytest

from pybi.semanticmodel.semanticmodel import SemanticModel

# ---------------------------------------------------------------------------
# Sample directory paths
# ---------------------------------------------------------------------------

_SAMPLES_ROOT = Path("../pbi-samples/pbi/pbir/11.25")

_SAMPLE_DIRS: dict[str, Path] = {
    "ai": _SAMPLES_ROOT / "ai" / "Artificial Intelligence Sample.SemanticModel",
    "human-resources": _SAMPLES_ROOT
    / "human-resources"
    / "Human Resources Sample PBIX.SemanticModel",
    "covid-19-us": _SAMPLES_ROOT
    / "covid-19-us"
    / "COVID-19 US Tracking Sample.SemanticModel",
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


def _roundtrip(sample_name: str):
    """Read a sample, write it, read it back, return (original, roundtripped)."""
    sm = SemanticModel.read(str(_SAMPLE_DIRS[sample_name]))
    with tempfile.TemporaryDirectory() as tmpdir:
        sm.write(tmpdir)
        sm2 = SemanticModel.read(tmpdir)
    return sm, sm2


def _expr_str(expr) -> str:
    """Normalize expression to a comparable string."""
    if expr is None:
        return ""
    if isinstance(expr, list):
        return "\n".join(expr)
    return expr


# ---------------------------------------------------------------------------
# TestWriteRoundtripAllSamples — parametrized across samples
# ---------------------------------------------------------------------------


class TestWriteRoundtripAllSamples:
    @pytest.fixture(
        params=sorted(_SAMPLE_DIRS.keys()),
        ids=lambda k: k,
    )
    def sample_name(self, request) -> str:
        return request.param

    @pytest.fixture
    def roundtripped(self, sample_name):
        return _roundtrip(sample_name)

    def test_write_and_reread_succeeds(self, roundtripped):
        """Write + re-read completes without error."""
        _, sm2 = roundtripped
        assert sm2 is not None

    def test_table_count_preserved(self, roundtripped):
        sm1, sm2 = roundtripped
        assert len(sm1.definition.model.tables) == len(sm2.definition.model.tables)

    def test_relationship_count_preserved(self, roundtripped):
        sm1, sm2 = roundtripped
        r1 = sm1.definition.model.relationships or []
        r2 = sm2.definition.model.relationships or []
        assert len(r1) == len(r2)

    def test_expression_count_preserved(self, roundtripped):
        sm1, sm2 = roundtripped
        assert len(sm1.definition.model.expressions) == len(
            sm2.definition.model.expressions
        )

    def test_culture_count_preserved(self, roundtripped):
        sm1, sm2 = roundtripped
        assert len(sm1.definition.model.cultures) == len(sm2.definition.model.cultures)

    def test_compatibility_level_preserved(self, roundtripped):
        sm1, sm2 = roundtripped
        assert sm1.definition.compatibilityLevel == sm2.definition.compatibilityLevel

    def test_all_table_names_preserved(self, roundtripped):
        sm1, sm2 = roundtripped
        names1 = {t.name for t in sm1.definition.model.tables}
        names2 = {t.name for t in sm2.definition.model.tables}
        assert names1 == names2

    def test_column_counts_preserved(self, roundtripped):
        sm1, sm2 = roundtripped
        for t1 in sm1.definition.model.tables:
            t2 = next(t for t in sm2.definition.model.tables if t.name == t1.name)
            c1 = len(t1.columns or [])
            c2 = len(t2.columns or [])
            assert c1 == c2, f"Table {t1.name}: {c1} cols -> {c2}"

    def test_measure_counts_preserved(self, roundtripped):
        sm1, sm2 = roundtripped
        for t1 in sm1.definition.model.tables:
            t2 = next(t for t in sm2.definition.model.tables if t.name == t1.name)
            m1 = len(t1.measures or [])
            m2 = len(t2.measures or [])
            assert m1 == m2, f"Table {t1.name}: {m1} measures -> {m2}"

    def test_partition_counts_preserved(self, roundtripped):
        sm1, sm2 = roundtripped
        for t1 in sm1.definition.model.tables:
            t2 = next(t for t in sm2.definition.model.tables if t.name == t1.name)
            assert len(t1.partitions) == len(t2.partitions), (
                f"Table {t1.name}: partitions mismatch"
            )

    def test_hierarchy_level_counts_preserved(self, roundtripped):
        sm1, sm2 = roundtripped
        for t1 in sm1.definition.model.tables:
            t2 = next(t for t in sm2.definition.model.tables if t.name == t1.name)
            h1 = t1.hierarchies or []
            h2 = t2.hierarchies or []
            assert len(h1) == len(h2), f"Table {t1.name}: hierarchy count mismatch"
            for ha, hb in zip(h1, h2):
                la = ha.get("levels") or ha.get("level") or []
                lb = hb.get("levels") or hb.get("level") or []
                assert len(la) == len(lb), (
                    f"Table {t1.name}, hierarchy {ha.get('name')}: "
                    f"{len(la)} levels -> {len(lb)}"
                )


# ---------------------------------------------------------------------------
# TestWriteRoundtripColumnDetails
# ---------------------------------------------------------------------------


class TestWriteRoundtripColumnDetails:
    @pytest.fixture(
        params=sorted(_SAMPLE_DIRS.keys()),
        ids=lambda k: k,
    )
    def sample_name(self, request) -> str:
        return request.param

    @pytest.fixture
    def roundtripped(self, sample_name):
        return _roundtrip(sample_name)

    def test_column_expressions_preserved(self, roundtripped):
        sm1, sm2 = roundtripped
        for t1 in sm1.definition.model.tables:
            t2 = next(t for t in sm2.definition.model.tables if t.name == t1.name)
            for c1 in t1.columns or []:
                c2 = next((c for c in (t2.columns or []) if c.name == c1.name), None)
                assert c2 is not None, f"Missing column {t1.name}.{c1.name}"
                assert c1.expression == c2.expression, (
                    f"Expression mismatch: {t1.name}.{c1.name}"
                )

    def test_column_types_preserved(self, roundtripped):
        sm1, sm2 = roundtripped
        for t1 in sm1.definition.model.tables:
            t2 = next(t for t in sm2.definition.model.tables if t.name == t1.name)
            for c1 in t1.columns or []:
                c2 = next(c for c in (t2.columns or []) if c.name == c1.name)
                assert c1.type == c2.type, (
                    f"Type mismatch: {t1.name}.{c1.name}: {c1.type} -> {c2.type}"
                )

    def test_column_annotations_preserved(self, roundtripped):
        sm1, sm2 = roundtripped
        for t1 in sm1.definition.model.tables:
            t2 = next(t for t in sm2.definition.model.tables if t.name == t1.name)
            for c1 in t1.columns or []:
                c2 = next(c for c in (t2.columns or []) if c.name == c1.name)
                assert c1.annotations == c2.annotations, (
                    f"Annotation mismatch: {t1.name}.{c1.name}"
                )

    def test_column_variations_preserved(self, roundtripped):
        sm1, sm2 = roundtripped
        for t1 in sm1.definition.model.tables:
            t2 = next(t for t in sm2.definition.model.tables if t.name == t1.name)
            for c1 in t1.columns or []:
                c2 = next(c for c in (t2.columns or []) if c.name == c1.name)
                has_var1 = c1.variations is not None
                has_var2 = c2.variations is not None
                assert has_var1 == has_var2, f"Variation mismatch: {t1.name}.{c1.name}"


# ---------------------------------------------------------------------------
# TestWriteRoundtripMeasureDetails
# ---------------------------------------------------------------------------


class TestWriteRoundtripMeasureDetails:
    @pytest.fixture(
        params=sorted(_SAMPLE_DIRS.keys()),
        ids=lambda k: k,
    )
    def sample_name(self, request) -> str:
        return request.param

    @pytest.fixture
    def roundtripped(self, sample_name):
        return _roundtrip(sample_name)

    def test_measure_expressions_preserved(self, roundtripped):
        sm1, sm2 = roundtripped
        for t1 in sm1.definition.model.tables:
            t2 = next(t for t in sm2.definition.model.tables if t.name == t1.name)
            for m1 in t1.measures or []:
                m2 = next((m for m in (t2.measures or []) if m.name == m1.name), None)
                assert m2 is not None, f"Missing measure {t1.name}.{m1.name}"
                assert _expr_str(m1.expression) == _expr_str(m2.expression), (
                    f"Expression mismatch: {t1.name}.{m1.name}"
                )

    def test_measure_format_strings_preserved(self, roundtripped):
        sm1, sm2 = roundtripped
        for t1 in sm1.definition.model.tables:
            t2 = next(t for t in sm2.definition.model.tables if t.name == t1.name)
            for m1 in t1.measures or []:
                m2 = next(m for m in (t2.measures or []) if m.name == m1.name)
                assert m1.formatString == m2.formatString, (
                    f"formatString mismatch: {t1.name}.{m1.name}: "
                    f"{m1.formatString!r} -> {m2.formatString!r}"
                )


# ---------------------------------------------------------------------------
# TestWriteRoundtripRelationshipDetails
# ---------------------------------------------------------------------------


class TestWriteRoundtripRelationshipDetails:
    @pytest.fixture(scope="class")
    def roundtripped(self):
        return _roundtrip("ai")

    def test_relationship_endpoints_preserved(self, roundtripped):
        sm1, sm2 = roundtripped
        for r1 in sm1.definition.model.relationships:
            r2 = next(
                r for r in sm2.definition.model.relationships if r.name == r1.name
            )
            assert r1.fromTable == r2.fromTable, f"fromTable: {r1.name}"
            assert r1.fromColumn == r2.fromColumn, f"fromColumn: {r1.name}"
            assert r1.toTable == r2.toTable, f"toTable: {r1.name}"
            assert r1.toColumn == r2.toColumn, f"toColumn: {r1.name}"

    def test_relationship_properties_preserved(self, roundtripped):
        sm1, sm2 = roundtripped
        for r1 in sm1.definition.model.relationships:
            r2 = next(
                r for r in sm2.definition.model.relationships if r.name == r1.name
            )
            assert r1.isActive == r2.isActive, f"isActive: {r1.name}"
            assert r1.joinOnDateBehavior == r2.joinOnDateBehavior, (
                f"joinOnDateBehavior: {r1.name}"
            )


# ---------------------------------------------------------------------------
# TestWriteRoundtripAISample — targeted assertions
# ---------------------------------------------------------------------------


class TestWriteRoundtripAISample:
    @pytest.fixture(scope="class")
    def roundtripped(self):
        return _roundtrip("ai")

    def test_accounts_hierarchy_levels(self, roundtripped):
        _, sm2 = roundtripped
        t = next(t for t in sm2.definition.model.tables if t.name == "Accounts")
        assert t.hierarchies is not None
        hier = t.hierarchies[0]
        assert hier["name"] == "Location Hierarchy"
        levels = hier.get("levels") or hier.get("level") or []
        assert len(levels) == 5

    def test_accounts_calculated_column(self, roundtripped):
        _, sm2 = roundtripped
        t = next(t for t in sm2.definition.model.tables if t.name == "Accounts")
        col = next(c for c in t.columns if c.name == "Industry Lookup")
        assert col.expression is not None
        assert col.type == "calculated"

    def test_opportunities_variation(self, roundtripped):
        _, sm2 = roundtripped
        t = next(t for t in sm2.definition.model.tables if t.name == "Opportunities")
        col = next(c for c in t.columns if c.name == "Opportunity Created On")
        assert col.variations is not None
        assert len(col.variations) == 1

    def test_backtick_measure_preserved(self, roundtripped):
        sm1, sm2 = roundtripped
        t1 = next(t for t in sm1.definition.model.tables if t.name == "Opportunities")
        t2 = next(t for t in sm2.definition.model.tables if t.name == "Opportunities")
        m1 = next(m for m in t1.measures if m.name == "Revenue Won")
        m2 = next(m for m in t2.measures if m.name == "Revenue Won")
        assert _expr_str(m1.expression) == _expr_str(m2.expression)
        assert m1.formatString == m2.formatString
