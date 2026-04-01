"""Integration tests for the TMDL parser against real sample files."""

from pathlib import Path

import pytest

from pybi.serialization.parsers.tmdl.parser import (
    ObjectDeclaration,
    PropertyNode,
    parse_tmdl,
)

# ---------------------------------------------------------------------------
# Paths to sample semantic models (relative to project root)
# ---------------------------------------------------------------------------

_AI = Path(
    "../pbi-samples/pbi/pbir/11.25/ai/Artificial Intelligence Sample.SemanticModel/definition"
)
_HUMAN_RESOURCES = Path(
    "../pbi-samples/pbi/pbir/11.25/human-resources"
    "/Human Resources Sample PBIX.SemanticModel/definition"
)

pytestmark = pytest.mark.skipif(
    not Path("../pbi-samples").exists(),
    reason="pbi-samples repository not available; clone https://github.com/willianmh/pbi-samples",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_file(path: Path) -> list[ObjectDeclaration]:
    text = path.read_text(encoding="utf-8")
    return parse_tmdl(text, file_path=str(path))


def _collect_all_nodes(nodes: list[ObjectDeclaration]) -> list[ObjectDeclaration]:
    """Recursively collect all ObjectDeclaration nodes in the tree."""
    result = []
    for node in nodes:
        result.append(node)
        result.extend(_collect_all_nodes(node.children))
    return result


def _collect_all_properties(nodes: list[ObjectDeclaration]) -> list[PropertyNode]:
    """Recursively collect all PropertyNode instances."""
    props = []
    for node in _collect_all_nodes(nodes):
        props.extend(node.properties)
    return props


def _collect_all_annotations(nodes: list[ObjectDeclaration]) -> list[ObjectDeclaration]:
    """Recursively collect all annotation ObjectDeclaration children."""
    anns = []
    for node in _collect_all_nodes(nodes):
        anns.extend(c for c in node.children if c.object_type == "annotation")
    return anns


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def samples_dir() -> Path:
    return Path("../pbi-samples/pbi/pbir/11.25")


@pytest.fixture(scope="session")
def all_tmdl_files(samples_dir: Path) -> list[Path]:
    return sorted(samples_dir.glob("**/*.tmdl"))


# ---------------------------------------------------------------------------
# TestParserOnAllSamples
#
# Each test is parametrized per file so failures are isolated.
# ---------------------------------------------------------------------------


class TestParserOnAllSamples:
    @pytest.fixture(
        params=sorted(Path("../pbi-samples/pbi/pbir/11.25").glob("**/*.tmdl"))
        if Path("../pbi-samples").exists()
        else [],
        ids=lambda p: p.name,
    )
    def tmdl_file(self, request) -> Path:
        return request.param

    @pytest.fixture
    def parsed_nodes(self, tmdl_file: Path) -> list[ObjectDeclaration]:
        """Pre-parsed nodes for a single file."""
        try:
            return _parse_file(tmdl_file)
        except Exception as e:
            pytest.xfail(f"Parser error in {tmdl_file.name}: {e}")

    def test_no_crash_on_all_samples(self, tmdl_file: Path):
        """Smoke test: every .tmdl file must parse without error."""
        _parse_file(tmdl_file)  # must not raise

    def test_all_nodes_have_object_type(self, parsed_nodes, tmdl_file: Path):
        for node in _collect_all_nodes(parsed_nodes):
            assert node.object_type, (
                f"Empty object_type in {tmdl_file.name} at line {node.line}"
            )

    def test_all_nodes_have_valid_line_numbers(self, parsed_nodes, tmdl_file: Path):
        for node in _collect_all_nodes(parsed_nodes):
            assert node.line >= 1, (
                f"Node with line < 1 in {tmdl_file.name}: "
                f"{node.object_type} {node.name}"
            )

    def test_no_empty_property_keys(self, parsed_nodes, tmdl_file: Path):
        for prop in _collect_all_properties(parsed_nodes):
            assert prop.key, (
                f"Empty property key in {tmdl_file.name} at line {prop.line}"
            )

    def test_no_empty_annotation_names(self, parsed_nodes, tmdl_file: Path):
        for ann in _collect_all_annotations(parsed_nodes):
            assert ann.name, (
                f"Empty annotation name in {tmdl_file.name} at line {ann.line}"
            )

    def test_children_are_object_declarations(self, parsed_nodes, tmdl_file: Path):
        for node in _collect_all_nodes(parsed_nodes):
            for child in node.children:
                assert isinstance(child, ObjectDeclaration), (
                    f"Non-ObjectDeclaration child in {tmdl_file.name}: {type(child)}"
                )


# ---------------------------------------------------------------------------
# TestParserSpecificSamples
# ---------------------------------------------------------------------------


class TestParserSpecificSamples:
    """Targeted assertions on specific known sample files."""

    def test_database_tmdl_structure(self):
        """database.tmdl: 1 node, object_type='database', no name, compatibilityLevel."""
        nodes = _parse_file(_AI / "database.tmdl")
        assert len(nodes) == 1
        db = nodes[0]
        assert db.object_type == "database"
        assert db.name is None
        props = {p.key: p.value for p in db.properties}
        assert props["compatibilityLevel"] == "1567"

    def test_model_tmdl_has_model_and_refs(self):
        """model.tmdl: first node is 'model', remaining include refs and annotations."""
        nodes = _parse_file(_AI / "model.tmdl")
        assert nodes[0].object_type == "model"
        assert nodes[0].name == "Model"
        types = {n.object_type for n in nodes}
        assert "ref" in types
        assert "annotation" in types

    def test_model_annotations_count(self):
        """AI model.tmdl has exactly 4 top-level annotations."""
        nodes = _parse_file(_AI / "model.tmdl")
        ann_nodes = [n for n in nodes if n.object_type == "annotation"]
        assert len(ann_nodes) == 4

    def test_model_ref_count(self):
        """AI model.tmdl has 18 ref table + 1 ref cultureInfo = 19 refs."""
        nodes = _parse_file(_AI / "model.tmdl")
        ref_nodes = [n for n in nodes if n.object_type == "ref"]
        assert len(ref_nodes) == 19
        table_refs = [n for n in ref_nodes if n.name and n.name.startswith("table ")]
        culture_refs = [
            n for n in ref_nodes if n.name and n.name.startswith("cultureInfo ")
        ]
        assert len(table_refs) == 18
        assert len(culture_refs) == 1

    def test_model_data_access_options(self):
        """AI model.tmdl: Model has dataAccessOptions child with flag properties."""
        nodes = _parse_file(_AI / "model.tmdl")
        model_node = nodes[0]
        assert model_node.object_type == "model"
        dao = next(
            (c for c in model_node.children if c.object_type == "dataAccessOptions"),
            None,
        )
        assert dao is not None, "dataAccessOptions child not found"
        prop_keys = {p.key for p in dao.properties}
        assert "legacyRedirects" in prop_keys
        assert "returnErrorValuesAsNull" in prop_keys

    def test_relationships_count(self):
        """AI relationships.tmdl has 17 relationship nodes."""
        nodes = _parse_file(_AI / "relationships.tmdl")
        assert len(nodes) == 17
        assert all(n.object_type == "relationship" for n in nodes)

    def test_relationships_inactive_property(self):
        """At least 2 relationships have isActive: false."""
        nodes = _parse_file(_AI / "relationships.tmdl")
        inactive = [
            n
            for n in nodes
            if any(p.key == "isActive" and p.value == "false" for p in n.properties)
        ]
        assert len(inactive) >= 2

    def test_relationships_join_on_date_behavior(self):
        """At least 5 relationships have joinOnDateBehavior property."""
        nodes = _parse_file(_AI / "relationships.tmdl")
        with_jodb = [
            n for n in nodes if any(p.key == "joinOnDateBehavior" for p in n.properties)
        ]
        assert len(with_jodb) >= 5

    def test_accounts_hierarchy(self):
        """Accounts.tmdl: table has a hierarchy child with 5 level children."""
        nodes = _parse_file(_AI / "tables" / "Accounts.tmdl")
        table = nodes[0]
        hierarchies = [c for c in table.children if c.object_type == "hierarchy"]
        assert len(hierarchies) == 1
        hier = hierarchies[0]
        assert hier.name == "Location Hierarchy"
        levels = [c for c in hier.children if c.object_type == "level"]
        assert len(levels) == 5

    def test_accounts_column_count(self):
        """Accounts.tmdl: expected number of column children."""
        nodes = _parse_file(_AI / "tables" / "Accounts.tmdl")
        table = nodes[0]
        columns = [c for c in table.children if c.object_type == "column"]
        # Accounts has many columns (Account Name, Street, City, etc.)
        assert len(columns) >= 15

    def test_accounts_calculated_column(self):
        """Accounts.tmdl: 'Industry Lookup' is a calculated column."""
        nodes = _parse_file(_AI / "tables" / "Accounts.tmdl")
        table = nodes[0]
        calc_cols = [
            c
            for c in table.children
            if c.object_type == "column" and c.expression is not None
        ]
        assert len(calc_cols) >= 1
        lookup_col = next((c for c in calc_cols if c.name == "Industry Lookup"), None)
        assert lookup_col is not None, "'Industry Lookup' calculated column not found"
        assert "LOOKUPVALUE" in lookup_col.expression

    def test_accounts_partition_m(self):
        """Accounts.tmdl: partition with 'm' expression."""
        nodes = _parse_file(_AI / "tables" / "Accounts.tmdl")
        table = nodes[0]
        partitions = [c for c in table.children if c.object_type == "partition"]
        assert len(partitions) >= 1
        assert partitions[0].expression == "m"

    def test_opportunities_backtick_measures(self):
        """Opportunities.tmdl: measures with backtick expressions have non-empty expression."""
        nodes = _parse_file(_AI / "tables" / "Opportunities.tmdl")
        table = nodes[0]
        measures = [c for c in table.children if c.object_type == "measure"]
        measures_with_expr = [m for m in measures if m.expression]
        assert len(measures_with_expr) >= 5
        # At least some should have multi-line content (from backtick blocks)
        multiline = [m for m in measures_with_expr if "\n" in (m.expression or "")]
        assert len(multiline) >= 1, (
            "Expected at least one multi-line measure expression"
        )

    def test_opportunities_multiline_measure(self):
        """'Opportunity Count' measure has multi-line expression (indented, not backtick)."""
        nodes = _parse_file(_AI / "tables" / "Opportunities.tmdl")
        table = nodes[0]
        m = next(
            (
                c
                for c in table.children
                if c.object_type == "measure" and c.name == "Opportunity Count"
            ),
            None,
        )
        assert m is not None, "'Opportunity Count' measure not found"
        assert m.expression is not None
        assert "COUNTAX" in m.expression

    def test_opportunities_variation(self):
        """Column 'Opportunity Created On' has a variation child."""
        nodes = _parse_file(_AI / "tables" / "Opportunities.tmdl")
        table = nodes[0]
        col = next(
            (
                c
                for c in table.children
                if c.object_type == "column" and c.name == "Opportunity Created On"
            ),
            None,
        )
        assert col is not None
        variations = [c for c in col.children if c.object_type == "variation"]
        assert len(variations) == 1
        var = variations[0]
        assert var.name == "Variation"
        prop_keys = {p.key for p in var.properties}
        assert "isDefault" in prop_keys
        assert "relationship" in prop_keys
        assert "defaultHierarchy" in prop_keys

    def test_opportunities_calculated_columns(self):
        """'Weeks Open' and 'Days Remaining In Pipeline' are calculated columns."""
        nodes = _parse_file(_AI / "tables" / "Opportunities.tmdl")
        table = nodes[0]
        calc_col_names = {
            c.name
            for c in table.children
            if c.object_type == "column" and c.expression is not None
        }
        assert "Weeks Open" in calc_col_names
        assert "Days Remaining In Pipeline" in calc_col_names

    def test_opportunities_boolean_format_string(self):
        """'Decision Maker Identified' has boolean format string with doubled quotes."""
        nodes = _parse_file(_AI / "tables" / "Opportunities.tmdl")
        table = nodes[0]
        col = next(
            (
                c
                for c in table.children
                if c.object_type == "column" and c.name == "Decision Maker Identified"
            ),
            None,
        )
        assert col is not None
        fmt_prop = next((p for p in col.properties if p.key == "formatString"), None)
        assert fmt_prop is not None
        assert isinstance(fmt_prop.value, str)
        assert "TRUE" in fmt_prop.value

    def test_opportunities_annotations_json(self):
        """Annotation values containing JSON are preserved as strings."""
        nodes = _parse_file(_AI / "tables" / "Opportunities.tmdl")
        all_anns = _collect_all_annotations(nodes)
        json_anns = [a for a in all_anns if a.expression and "{" in a.expression]
        assert len(json_anns) >= 1
        for ann in json_anns:
            assert isinstance(ann.expression, str)

    def test_expressions_multiline_m(self):
        """expressions.tmdl: Query1 has multi-line M expression body."""
        nodes = _parse_file(_AI / "expressions.tmdl")
        q1 = next(
            (n for n in nodes if n.object_type == "expression" and n.name == "Query1"),
            None,
        )
        assert q1 is not None, "Query1 expression not found"
        assert q1.expression is not None
        assert "let" in q1.expression.lower() or "Let" in q1.expression

    def test_expressions_annotations(self):
        """expressions.tmdl: Query1 has annotations."""
        nodes = _parse_file(_AI / "expressions.tmdl")
        q1 = next(n for n in nodes if n.name == "Query1")
        ann_children = [c for c in q1.children if c.object_type == "annotation"]
        ann_names = {a.name for a in ann_children}
        assert "PBI_NavigationStepName" in ann_names
        assert "PBI_ResultType" in ann_names

    def test_human_resources_model_data_access_options(self):
        """HR model.tmdl: Model has dataAccessOptions child."""
        nodes = _parse_file(_HUMAN_RESOURCES / "model.tmdl")
        model = nodes[0]
        dao = next(
            (c for c in model.children if c.object_type == "dataAccessOptions"),
            None,
        )
        assert dao is not None
        prop_keys = {p.key for p in dao.properties}
        assert "legacyRedirects" in prop_keys
        assert "returnErrorValuesAsNull" in prop_keys


# ---------------------------------------------------------------------------
# TestParserStructuralInvariants
#
# Cross-cutting invariants scanned across all sample files.
# ---------------------------------------------------------------------------


class TestParserStructuralInvariants:
    def test_table_files_produce_one_table(self, all_tmdl_files):
        """Every file in tables/ yields exactly 1 node with object_type='table'."""
        for path in all_tmdl_files:
            if "/tables/" not in str(path):
                continue
            nodes = _parse_file(path)
            tables = [n for n in nodes if n.object_type == "table"]
            assert len(tables) == 1, (
                f"Expected 1 table node in {path.name}, got {len(tables)}"
            )

    def test_database_files_produce_one_database(self, all_tmdl_files):
        """Every database.tmdl yields 1 node with object_type='database'."""
        for path in all_tmdl_files:
            if path.name != "database.tmdl":
                continue
            nodes = _parse_file(path)
            dbs = [n for n in nodes if n.object_type == "database"]
            assert len(dbs) == 1, f"Expected 1 database node in {path}, got {len(dbs)}"

    def test_relationship_files_produce_only_relationships(self, all_tmdl_files):
        """Every relationships.tmdl yields only 'relationship' nodes."""
        for path in all_tmdl_files:
            if path.name != "relationships.tmdl":
                continue
            nodes = _parse_file(path)
            for node in nodes:
                assert node.object_type == "relationship", (
                    f"Non-relationship node {node.object_type!r} in {path}"
                )

    def test_expression_files_produce_only_expressions(self, all_tmdl_files):
        """Every expressions.tmdl yields only 'expression' nodes."""
        for path in all_tmdl_files:
            if path.name != "expressions.tmdl":
                continue
            nodes = _parse_file(path)
            for node in nodes:
                assert node.object_type == "expression", (
                    f"Non-expression node {node.object_type!r} in {path}"
                )

    def test_annotation_values_are_strings(self, all_tmdl_files):
        """All annotation expression values are str or None type."""
        for path in all_tmdl_files:
            try:
                nodes = _parse_file(path)
            except Exception:
                continue
            for ann in _collect_all_annotations(nodes):
                assert ann.expression is None or isinstance(ann.expression, str), (
                    f"Non-string annotation expression in {path.name} "
                    f"at line {ann.line}: {type(ann.expression)}"
                )

    def test_no_none_property_keys(self, all_tmdl_files):
        """All PropertyNode.key values are non-None strings."""
        for path in all_tmdl_files:
            try:
                nodes = _parse_file(path)
            except Exception:
                continue
            for prop in _collect_all_properties(nodes):
                assert prop.key is not None and isinstance(prop.key, str), (
                    f"None or non-string property key in {path.name} "
                    f"at line {prop.line}"
                )

    def test_model_files_have_model_node(self, all_tmdl_files):
        """Every model.tmdl file contains at least one 'model' node."""
        for path in all_tmdl_files:
            if path.name != "model.tmdl":
                continue
            nodes = _parse_file(path)
            model_nodes = [n for n in nodes if n.object_type == "model"]
            assert len(model_nodes) >= 1, f"No model node in {path}"

    def test_all_tables_have_at_least_one_child(self, all_tmdl_files):
        """Every table in table files has at least one child (column, measure, or partition)."""
        for path in all_tmdl_files:
            if "/tables/" not in str(path):
                continue
            nodes = _parse_file(path)
            for node in nodes:
                if node.object_type == "table":
                    assert len(node.children) >= 1 or len(node.properties) >= 1, (
                        f"Table {node.name} in {path.name} has no content"
                    )
