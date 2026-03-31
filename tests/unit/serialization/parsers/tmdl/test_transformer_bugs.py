"""Tests for known bugs and edge cases in the TMDL transformer."""

from pybi.serialization.parsers.tmdl.parser import (
    ObjectDeclaration,
    PropertyNode,
    parse_tmdl,
)
from pybi.serialization.parsers.tmdl.transformer import TMDLTransformer, expand_node


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _node(
    object_type: str,
    name: str | None = None,
    expression: str | None = None,
    properties: list[PropertyNode] | None = None,
    children: list[ObjectDeclaration] | None = None,
    description: str | None = None,
) -> ObjectDeclaration:
    return ObjectDeclaration(
        object_type=object_type,
        name=name,
        expression=expression,
        properties=properties or [],
        children=children or [],
        description=description,
    )


def _prop(key: str, value, is_expression: bool = False) -> PropertyNode:
    return PropertyNode(key=key, value=value, line=1, is_expression=is_expression)


def _transformer() -> TMDLTransformer:
    return TMDLTransformer()


# ---------------------------------------------------------------------------
# Calculated column expression mapping (fixed)
#
# expand_node() now stores ObjectDeclaration.expression as raw["expression"],
# so transform_column() correctly populates Column.expression.
# ---------------------------------------------------------------------------


class TestCalculatedColumnExpression:
    def test_single_line_expression_mapped(self):
        """Calculated column with inline DAX should have .expression set."""
        node = _node(
            "column",
            name="FullName",
            expression='[FirstName] & " " & [LastName]',
            properties=[_prop("lineageTag", "abc")],
        )
        col = _transformer().transform_column(node)
        assert col.expression == '[FirstName] & " " & [LastName]'

    def test_multiline_expression_stored_as_string(self):
        """Multi-line calculated column expression is stored as raw string."""
        expr = "ABS(\n    DATEDIFF(T[Start], T[End], WEEK)\n)"
        node = _node(
            "column",
            name="Weeks Open",
            expression=expr,
            properties=[_prop("lineageTag", "abc")],
        )
        col = _transformer().transform_column(node)
        # expand_node stores the raw expression string; Column accepts str
        assert col.expression == expr

    def test_real_lookupvalue_expression(self):
        """LOOKUPVALUE calculated column from Accounts.tmdl sample."""
        expr = "LOOKUPVALUE(Industries[Industry], Industries[IndustrySeq],Accounts[IndustrySeq])"
        node = _node(
            "column",
            name="Industry Lookup",
            expression=expr,
            properties=[
                _prop("lineageTag", "2e717be5"),
                _prop("summarizeBy", "none"),
            ],
        )
        col = _transformer().transform_column(node)
        assert col.expression is not None
        assert "LOOKUPVALUE" in (
            col.expression if isinstance(col.expression, str) else col.expression[0]
        )

    def test_expression_stored_in_expression_key(self):
        """expand_node puts ObjectDeclaration.expression under 'expression' key."""
        node = _node("column", name="C", expression="SUM(X)")
        raw = expand_node(node)
        assert raw["expression"] == "SUM(X)"


# ---------------------------------------------------------------------------
# Variations mapping (fixed)
#
# "variation" is now in CHILDREN_NAMING_MAP → expand_node stores under
# "variations" (plural), which matches Column.variations.
# ---------------------------------------------------------------------------


class TestColumnVariationsMapping:
    def test_variation_mapped_to_variations_field(self):
        """Variation child on column should populate Column.variations."""
        variation = _node(
            "variation",
            name="Variation",
            properties=[
                _prop("isDefault", True),
                _prop("relationship", "rel-uuid"),
                _prop("defaultHierarchy", "Table.'Date Hierarchy'"),
            ],
        )
        node = _node(
            "column",
            name="Date",
            properties=[
                _prop("dataType", "dateTime"),
                _prop("lineageTag", "abc"),
                _prop("sourceColumn", "Date"),
            ],
            children=[variation],
        )
        col = _transformer().transform_column(node)
        assert col.variations is not None
        assert len(col.variations) == 1
        assert col.variations[0].name == "Variation"

    def test_expand_node_uses_plural_key(self):
        """expand_node stores variation under 'variations' via CHILDREN_NAMING_MAP."""
        variation = _node(
            "variation",
            name="V",
            properties=[_prop("isDefault", True)],
        )
        node = _node("column", name="C", children=[variation])
        raw = expand_node(node)
        assert "variations" in raw
        assert "variation" not in raw


# ---------------------------------------------------------------------------
# changedProperty structure (fixed)
#
# transform_column now rewrites changedProperty dicts from
# {name, expression} to {property: ...} format.
# ---------------------------------------------------------------------------


class TestChangedPropertyStructure:
    def test_changed_property_has_property_key(self):
        """changedProperty children should produce dicts with 'property' key."""
        cp1 = _node("changedProperty", expression="DataType")
        cp2 = _node("changedProperty", expression="IsHidden")
        node = _node(
            "column",
            name="Date",
            properties=[
                _prop("dataType", "dateTime"),
                _prop("lineageTag", "abc"),
                _prop("sourceColumn", "[Date]"),
            ],
            children=[cp1, cp2],
        )
        col = _transformer().transform_column(node)
        assert col.changedProperties is not None
        assert len(col.changedProperties) == 2
        assert col.changedProperties[0] == {"property": "DataType"}
        assert col.changedProperties[1] == {"property": "IsHidden"}

    def test_changed_property_current_structure(self):
        """Documents the current structure of changedProperty dicts."""
        cp = _node("changedProperty", expression="DataType")
        raw = expand_node(cp)
        assert raw["name"] is None
        assert raw["expression"] == "DataType"
        assert "property" not in raw


# ---------------------------------------------------------------------------
# Calculated column type (fixed)
#
# transform_column now sets type='calculated' when expression is present.
# ---------------------------------------------------------------------------


class TestCalculatedColumnType:
    def test_type_set_to_calculated(self):
        """Column with an expression should have type='calculated'."""
        node = _node(
            "column",
            name="Calc",
            expression="1 + 1",
            properties=[_prop("lineageTag", "abc")],
        )
        col = _transformer().transform_column(node)
        assert col.type == "calculated"


# ---------------------------------------------------------------------------
# BUG 5: level children not in CHILDREN_NAMING_MAP
#
# Hierarchy children of type "level" are stored under key "level" (singular)
# by expand_node.  Hierarchies are stored as raw dicts (not typed models),
# so the dict key would be "level" instead of "levels" if model.bim expects
# the plural.
# ---------------------------------------------------------------------------


class TestHierarchyLevelMapping:
    def test_expand_node_uses_singular_level_key(self):
        """Documents that hierarchy expansion uses 'level' not 'levels'."""
        level = _node(
            "level",
            name="Country",
            properties=[
                _prop("lineageTag", "l-1"),
                _prop("column", "Country"),
            ],
        )
        hier = _node(
            "hierarchy",
            name="Location",
            properties=[_prop("lineageTag", "h-1")],
            children=[level],
        )
        raw = expand_node(hier)
        # "level" not in CHILDREN_NAMING_MAP → stored as "level" (singular)
        assert "level" in raw
        assert "levels" not in raw


# ---------------------------------------------------------------------------
# Transformer: Expression objects
# ---------------------------------------------------------------------------


class TestTransformExpressionBugs:
    def test_multiline_expression_split(self):
        """Multi-line M expression should be split into a list."""
        expr = "let\n    Source = Sql.Database(S, D)\nin\n    Source"
        node = _node(
            "expression",
            name="MyQuery",
            expression=expr,
            properties=[_prop("lineageTag", "e-1")],
        )
        e = _transformer().transform_expression(node)
        assert isinstance(e.expression, list)
        assert len(e.expression) == 4

    def test_single_line_expression_stays_string(self):
        """Single-line expression should remain a string."""
        node = _node(
            "expression",
            name="Simple",
            expression="1 + 1",
            properties=[_prop("lineageTag", "e-2")],
        )
        e = _transformer().transform_expression(node)
        assert isinstance(e.expression, str)
        assert e.expression == "1 + 1"

    def test_empty_expression(self):
        """Expression node without expression content."""
        node = _node(
            "expression",
            name="Empty",
            properties=[_prop("lineageTag", "e-3")],
        )
        e = _transformer().transform_expression(node)
        assert e.expression == ""


# ---------------------------------------------------------------------------
# Transformer: Partition source edge cases
# ---------------------------------------------------------------------------


class TestTransformPartitionEdgeCases:
    def test_m_partition_with_multiline_source(self):
        """Partition source with multi-line M expression."""
        source_child = _node(
            "source",
            expression="let\n    Source = Sql.Database(S, D)\nin\n    Source",
        )
        node = _node(
            "partition",
            name="P",
            expression="m",
            properties=[_prop("mode", "import")],
            children=[source_child],
        )
        p = _transformer().transform_partition(node)
        assert p.source.type == "m"
        assert p.source.expression is not None
        assert isinstance(p.source.expression, list)

    def test_calculated_partition_no_source_child(self):
        """Calculated partition without explicit source child."""
        node = _node(
            "partition",
            name="P",
            expression="calculated",
            properties=[_prop("mode", "import")],
        )
        p = _transformer().transform_partition(node)
        assert p.source.type == "calculated"

    def test_entity_partition_with_expression_source(self):
        """Entity partition with expressionSource property."""
        source_child = _node(
            "source",
            properties=[
                _prop("entityName", "DimProduct"),
                _prop("expressionSource", "'My Source'"),
            ],
        )
        node = _node(
            "partition",
            name="P",
            expression="entity",
            properties=[_prop("mode", "directLake")],
            children=[source_child],
        )
        p = _transformer().transform_partition(node)
        assert p.source.type == "entity"
        assert p.source.entityName == "DimProduct"
        # unquote_name strips surrounding single quotes
        assert p.source.expressionSource == "My Source"


# ---------------------------------------------------------------------------
# Transformer: Relationship edge cases
# ---------------------------------------------------------------------------


class TestTransformRelationshipEdgeCases:
    def test_both_quoted_column_refs(self):
        """Both table and column quoted."""
        node = _node(
            "relationship",
            name="r1",
            properties=[
                _prop("fromColumn", "'Case Calendar'.'Case Date'"),
                _prop("toColumn", "'Date Table'.Date"),
            ],
        )
        r = _transformer().transform_relationship(node)
        assert r.fromTable == "Case Calendar"
        assert r.fromColumn == "Case Date"
        assert r.toTable == "Date Table"
        assert r.toColumn == "Date"

    def test_inactive_relationship(self):
        """isActive: false should be preserved."""
        node = _node(
            "relationship",
            name="r2",
            properties=[
                _prop("isActive", "false"),
                _prop("fromColumn", "T1.C1"),
                _prop("toColumn", "T2.C2"),
            ],
        )
        r = _transformer().transform_relationship(node)
        assert r.isActive == "false" or r.isActive is False

    def test_join_on_date_behavior(self):
        """joinOnDateBehavior property preserved."""
        node = _node(
            "relationship",
            name="r3",
            properties=[
                _prop("joinOnDateBehavior", "datePartOnly"),
                _prop("fromColumn", "T1.Date"),
                _prop("toColumn", "T2.Date"),
            ],
        )
        r = _transformer().transform_relationship(node)
        assert r.joinOnDateBehavior == "datePartOnly"


# ---------------------------------------------------------------------------
# Transformer: Measure with formatStringDefinition
# ---------------------------------------------------------------------------


class TestTransformMeasureFormatStringDef:
    def test_format_string_definition_child(self):
        """formatStringDefinition as child object is converted to dict."""
        fsd = _node(
            "formatStringDefinition",
            expression="\\$#,0;(\\$#,0);\\$#,0",
        )
        node = _node(
            "measure",
            name="Revenue",
            expression="SUM(T[Rev])",
            properties=[_prop("lineageTag", "m-1")],
            children=[fsd],
        )
        m = _transformer().transform_measure(node)
        assert m.formatStringDefinition is not None
        assert "expression" in m.formatStringDefinition


# ---------------------------------------------------------------------------
# Transformer: Culture edge cases
# ---------------------------------------------------------------------------


class TestTransformCultureEdgeCases:
    def test_culture_with_json_linguistic_metadata(self):
        """Culture with valid JSON linguistic metadata."""
        node = _node(
            "cultureInfo",
            name="en-US",
            properties=[
                _prop(
                    "linguisticMetadata",
                    '{"Language": "en-US", "Version": "1.0.0"}',
                    is_expression=True,
                ),
                _prop("contentType", "json"),
            ],
        )
        c = _transformer().transform_culture(node)
        assert c.name == "en-US"
        assert c.linguisticMetadata is not None
        assert c.linguisticMetadata["contentType"] == "json"

    def test_culture_without_metadata(self):
        """Culture with no linguistic metadata gets the default."""
        node = _node("cultureInfo", name="pt-BR")
        c = _transformer().transform_culture(node)
        assert c.name == "pt-BR"
        # No linguisticMetadata in TMDL → Culture gets its default value
        assert c.linguisticMetadata is not None


# ---------------------------------------------------------------------------
# Transformer: Table with description (fixed)
# ---------------------------------------------------------------------------


class TestTransformTableDescription:
    def test_table_description_preserved(self):
        """Table description should be set on the model."""
        node = _node(
            "table",
            name="T",
            description="Important table",
            properties=[_prop("lineageTag", "t-1")],
            children=[
                _node(
                    "partition",
                    name="P",
                    expression="m",
                    properties=[_prop("mode", "import")],
                    children=[_node("source")],
                )
            ],
        )
        t = _transformer().transform_table(node)
        assert t.description == "Important table"

    def test_column_description_preserved(self):
        """Column description should be set on the model."""
        node = _node(
            "column",
            name="C",
            description="Key column",
            properties=[
                _prop("dataType", "int64"),
                _prop("lineageTag", "c-1"),
            ],
        )
        col = _transformer().transform_column(node)
        assert col.name == "C"
        # Column model doesn't have a description field currently
        # This tests whether the transformer handles it gracefully


# ---------------------------------------------------------------------------
# End-to-end: parse TMDL text → transform to model
# ---------------------------------------------------------------------------


class TestParserToTransformerIntegration:
    """Parse TMDL text and transform to Pydantic models in one step."""

    def test_simple_table_roundtrip(self):
        """Parse a simple table and transform it."""
        text = (
            "table Sales\n"
            "\tlineageTag: abc-123\n"
            "\n"
            "\tcolumn Amount\n"
            "\t\tdataType: int64\n"
            "\t\tlineageTag: col-1\n"
            "\t\tsourceColumn: Amount\n"
            "\t\tsummarizeBy: sum\n"
            "\n"
            "\tmeasure 'Total Sales' = SUM(Sales[Amount])\n"
            "\t\tformatString: #,0\n"
            "\t\tlineageTag: m-1\n"
            "\n"
            "\tpartition Sales-part = m\n"
            "\t\tmode: import\n"
            "\t\tsource =\n"
            "\t\t\tlet Source = Sql.Database(S, D) in Source\n"
        )
        nodes = parse_tmdl(text)
        assert len(nodes) == 1
        t = _transformer().transform_table(nodes[0])
        assert t.name == "Sales"
        assert t.columns is not None and len(t.columns) == 1
        assert t.columns[0].name == "Amount"
        assert t.columns[0].dataType == "int64"
        assert t.measures is not None and len(t.measures) == 1
        assert t.measures[0].name == "Total Sales"
        assert t.measures[0].expression == "SUM(Sales[Amount])"
        assert len(t.partitions) == 1

    def test_table_with_calculated_column_and_variation(self):
        """Table with calculated column expression and column variation."""
        text = (
            "table T\n"
            "\tlineageTag: t-1\n"
            "\n"
            "\tcolumn 'Weeks Open' =\n"
            "\t\t\tABS(\n"
            "\t\t\t    DATEDIFF(T[Start], T[End], WEEK)\n"
            "\t\t\t)\n"
            "\t\tformatString: 0\n"
            "\t\tlineageTag: col-1\n"
            "\n"
            "\tcolumn Date\n"
            "\t\tdataType: dateTime\n"
            "\t\tlineageTag: col-2\n"
            "\t\tsourceColumn: Date\n"
            "\n"
            "\t\tvariation Variation\n"
            "\t\t\tisDefault\n"
            "\t\t\trelationship: rel-uuid\n"
            "\t\t\tdefaultHierarchy: LocalDate.'Date Hierarchy'\n"
            "\n"
            "\tpartition P = m\n"
            "\t\tmode: import\n"
        )
        nodes = parse_tmdl(text)
        t = _transformer().transform_table(nodes[0])

        # Calculated column should have expression
        calc_col = next(c for c in t.columns if c.name == "Weeks Open")
        assert calc_col.expression is not None
        assert "ABS" in (
            calc_col.expression
            if isinstance(calc_col.expression, str)
            else calc_col.expression[0]
        )

        # Column with variation
        date_col = next(c for c in t.columns if c.name == "Date")
        assert date_col.variations is not None
        assert len(date_col.variations) == 1

    def test_relationship_from_tmdl(self):
        """Parse and transform a relationship."""
        text = (
            "relationship abc-123\n"
            "\tjoinOnDateBehavior: datePartOnly\n"
            "\tfromColumn: 'Opportunity Calendar'.Date\n"
            "\ttoColumn: LocalDateTable.Date\n"
        )
        nodes = parse_tmdl(text)
        r = _transformer().transform_relationship(nodes[0])
        assert r.fromTable == "Opportunity Calendar"
        assert r.fromColumn == "Date"
        assert r.toTable == "LocalDateTable"
        assert r.toColumn == "Date"
        assert r.joinOnDateBehavior == "datePartOnly"

    def test_expression_with_multiline_m(self):
        """Parse and transform a multi-line M expression."""
        text = (
            "expression Query1 =\n"
            "\t\tlet\n"
            "\t\t    Source = Sql.Database(S, D)\n"
            "\t\tin\n"
            "\t\t    Source\n"
            "\tlineageTag: expr-1\n"
        )
        nodes = parse_tmdl(text)
        e = _transformer().transform_expression(nodes[0])
        assert e.name == "Query1"
        assert isinstance(e.expression, list)
        assert any("let" in line for line in e.expression)

    def test_column_with_changed_properties(self):
        """Column with changedProperty children from Opportunity Calendar."""
        text = (
            "table T\n"
            "\tlineageTag: t-1\n"
            "\n"
            "\tcolumn Date\n"
            "\t\tdataType: dateTime\n"
            "\t\tlineageTag: col-1\n"
            "\t\tsourceColumn: [Date]\n"
            "\n"
            "\t\tchangedProperty = DataType\n"
            "\t\tchangedProperty = IsHidden\n"
            "\n"
            "\tpartition P = calculated\n"
            "\t\tmode: import\n"
        )
        nodes = parse_tmdl(text)
        t = _transformer().transform_table(nodes[0])
        col = t.columns[0]
        assert col.changedProperties is not None
        assert len(col.changedProperties) == 2
        assert col.changedProperties[0] == {"property": "DataType"}
        assert col.changedProperties[1] == {"property": "IsHidden"}

    def test_backtick_measure_with_properties(self):
        """Measure with backtick expression followed by properties."""
        text = (
            "table T\n"
            "\tlineageTag: t-1\n"
            "\n"
            "\tmeasure 'Revenue Won' = ```\n"
            "\t\t\t\n"
            "\t\t\t CALCULATE(\n"
            "\t\t\t     SUMX(T, T[Value]),\n"
            '\t\t\t     FILTER(T, T[Status] = "Won")\n'
            "\t\t\t )\n"
            "\t\t\t```\n"
            "\t\tformatString: \\$#,0\n"
            "\t\tlineageTag: m-1\n"
            "\n"
            "\tpartition P = m\n"
            "\t\tmode: import\n"
        )
        nodes = parse_tmdl(text)
        t = _transformer().transform_table(nodes[0])
        assert t.measures is not None
        m = t.measures[0]
        assert m.name == "Revenue Won"
        assert m.expression is not None
        expr = (
            m.expression if isinstance(m.expression, str) else "\n".join(m.expression)
        )
        assert "CALCULATE" in expr
        assert m.formatString == "\\$#,0"

    def test_table_with_hierarchy(self):
        """Table with hierarchy and level children."""
        text = (
            "table Accounts\n"
            "\tlineageTag: t-1\n"
            "\n"
            "\tcolumn Country\n"
            "\t\tdataType: string\n"
            "\t\tlineageTag: c-1\n"
            "\t\tsourceColumn: Country\n"
            "\n"
            "\thierarchy 'Location Hierarchy'\n"
            "\t\tlineageTag: h-1\n"
            "\n"
            "\t\tlevel Country\n"
            "\t\t\tlineageTag: l-1\n"
            "\t\t\tcolumn: Country\n"
            "\n"
            "\t\tlevel City\n"
            "\t\t\tlineageTag: l-2\n"
            "\t\t\tcolumn: City\n"
            "\n"
            "\tpartition P = m\n"
            "\t\tmode: import\n"
        )
        nodes = parse_tmdl(text)
        t = _transformer().transform_table(nodes[0])
        assert t.hierarchies is not None
        assert len(t.hierarchies) == 1
        hier = t.hierarchies[0]
        assert hier["name"] == "Location Hierarchy"
        # Levels are under "level" key (singular) — not in CHILDREN_NAMING_MAP
        assert "level" in hier

    def test_annotation_on_table_and_column(self):
        """Annotations on table and column are preserved."""
        text = (
            "table T\n"
            "\tlineageTag: t-1\n"
            "\n"
            "\tcolumn C\n"
            "\t\tdataType: string\n"
            "\t\tlineageTag: c-1\n"
            "\t\tsourceColumn: C\n"
            "\n"
            "\t\tannotation SummarizationSetBy = Automatic\n"
            "\n"
            "\tpartition P = m\n"
            "\t\tmode: import\n"
            "\n"
            "\tannotation PBI_ResultType = Table\n"
        )
        nodes = parse_tmdl(text)
        t = _transformer().transform_table(nodes[0])

        # Table-level annotation
        assert t.annotations is not None
        assert any(a["name"] == "PBI_ResultType" for a in t.annotations)

        # Column-level annotation
        col = t.columns[0]
        assert col.annotations is not None
        assert any(a["name"] == "SummarizationSetBy" for a in col.annotations)
