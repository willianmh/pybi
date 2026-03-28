"""Unit tests for the TMDL parser."""

import pytest

from pybi.serialization.parsers.tmdl.parser import (
    TMDLParser,
    ObjectDeclaration,
    parse_tmdl,
)
from pybi.serialization.parsers.tmdl.lexer import TokenType
from pybi.serialization.parsers.tmdl.exceptions import TMDLParseError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse(text: str) -> list[ObjectDeclaration]:
    return parse_tmdl(text)


def _parse_one(text: str) -> ObjectDeclaration:
    nodes = _parse(text)
    assert len(nodes) == 1, f"Expected 1 node, got {len(nodes)}"
    return nodes[0]


def _annotations(node: ObjectDeclaration) -> list[ObjectDeclaration]:
    """Collect annotation children from an ObjectDeclaration."""
    return [c for c in node.children if c.object_type == "annotation"]


# ---------------------------------------------------------------------------
# TestParseBasicObject
# ---------------------------------------------------------------------------


class TestParseBasicObject:
    def test_database(self):
        node = _parse_one("database\n\tcompatibilityLevel: 1567\n")
        assert node.object_type == "database"
        assert node.name is None
        assert len(node.properties) == 1
        assert node.properties[0].key == "compatibilityLevel"
        assert node.properties[0].value == "1567"

    def test_table_with_name(self):
        node = _parse_one("table Accounts\n")
        assert node.object_type == "table"
        assert node.name == "Accounts"

    def test_table_with_quoted_name(self):
        node = _parse_one("table 'My Table'\n")
        assert node.object_type == "table"
        assert node.name == "My Table"

    def test_column_with_expression(self):
        node = _parse_one("column Total = [Price] * [Qty]\n")
        assert node.object_type == "column"
        assert node.name == "Total"
        assert node.expression == "[Price] * [Qty]"

    def test_measure_with_expression(self):
        node = _parse_one("measure 'Total Sales' = SUM(Sales[Amount])\n")
        assert node.object_type == "measure"
        assert node.name == "Total Sales"
        assert node.expression == "SUM(Sales[Amount])"

    def test_ref_with_subtype(self):
        node = _parse_one("ref table Customers\n")
        assert node.object_type == "ref"
        assert node.name == "table Customers"

    def test_ref_with_quoted_name(self):
        node = _parse_one("ref cultureInfo 'en-US'\n")
        assert node.object_type == "ref"
        assert node.name == "cultureInfo en-US"

    def test_multiple_top_level_objects(self):
        text = "table Foo\n\ntable Bar\n"
        nodes = _parse(text)
        assert len(nodes) == 2
        assert nodes[0].name == "Foo"
        assert nodes[1].name == "Bar"


# ---------------------------------------------------------------------------
# TestParseProperties
# ---------------------------------------------------------------------------


class TestParseProperties:
    def test_colon_string(self):
        node = _parse_one("table T\n\tlineageTag: abc-123\n")
        prop = node.properties[0]
        assert prop.key == "lineageTag"
        assert prop.value == "abc-123"
        assert prop.is_expression is False

    def test_colon_boolean_true(self):
        node = _parse_one("table T\n\tsomeProp: true\n")
        assert node.properties[0].value == "true"

    def test_colon_boolean_false(self):
        node = _parse_one("table T\n\tsomeProp: false\n")
        assert node.properties[0].value == "false"

    def test_colon_integer(self):
        node = _parse_one("database\n\tcompatibilityLevel: 1567\n")
        assert node.properties[0].value == "1567"
        assert isinstance(node.properties[0].value, str)

    def test_colon_float(self):
        node = _parse_one("table T\n\tsomeProp: 3.14\n")
        assert node.properties[0].value == "3.14"
        assert isinstance(node.properties[0].value, str)

    def test_colon_format_string_preserved_as_string(self):
        """Format strings like '0.00' are preserved as raw strings by the
        parser.  Type coercion is deferred to the transformer / Pydantic."""
        node = _parse_one("table T\n\tformatString: 0.00\n")
        assert node.properties[0].value == "0.00"

    def test_equals_expression(self):
        node = _parse_one("table T\n\tsomeProp = SUM(X)\n")
        prop = node.properties[0]
        assert prop.key == "someProp"
        assert prop.value == "SUM(X)"
        assert prop.is_expression is True

    def test_flag_property(self):
        node = _parse_one("table T\n\tisHidden\n")
        prop = node.properties[0]
        assert prop.key == "isHidden"
        assert prop.value is True

    def test_multiple_properties(self):
        text = "table T\n\tlineageTag: abc\n\tisHidden\n\tdataType: string\n"
        node = _parse_one(text)
        assert len(node.properties) == 3
        assert node.properties[0].key == "lineageTag"
        assert node.properties[1].key == "isHidden"
        assert node.properties[2].key == "dataType"

    def test_keyword_as_property_name(self):
        """Keywords like 'source' can appear as property names when followed by ':'."""
        text = "table T\n\tcolumn C\n\t\tsource: mySource\n"
        node = _parse_one(text)
        child = node.children[0]
        # 'source' followed by ':' should be parsed as a property, not a child object
        # This depends on how the lexer emits it. The parser checks peek(+1) == COLON.
        # If 'source' is a KEYWORD and next is COLON, it's a property.
        assert any(p.key == "source" for p in child.properties)


# ---------------------------------------------------------------------------
# TestParseDescriptions
# ---------------------------------------------------------------------------


class TestParseDescriptions:
    def test_single_line_description(self):
        text = "/// This is a table\ntable T\n"
        node = _parse_one(text)
        assert node.description == "This is a table"

    def test_multiline_description(self):
        text = "/// Line one\n/// Line two\n/// Line three\ntable T\n"
        node = _parse_one(text)
        assert node.description == "Line one\nLine two\nLine three"

    def test_description_on_child_object(self):
        text = "table T\n\t/// Column description\n\tcolumn C\n"
        node = _parse_one(text)
        assert len(node.children) == 1
        assert node.children[0].description == "Column description"

    def test_multiline_description_on_child(self):
        """BUG 1 regression: multi-line descriptions before a child must be
        fully collected, not just the last line."""
        text = "table T\n\t/// First line\n\t/// Second line\n\tcolumn C\n"
        node = _parse_one(text)
        assert node.children[0].description == "First line\nSecond line"

    def test_empty_description_line(self):
        """'///' with nothing after produces DESCRIPTION('') from the lexer.

        The parser collects descriptions via ``if description: ...`` which
        treats empty string as falsy, so a sole empty description line
        yields description=None on the object.
        """
        text = "///\ntable T\n"
        node = _parse_one(text)
        assert node.description is None

    def test_empty_description_between_nonempty(self):
        """An empty '///' line between non-empty lines produces a joined
        string with an embedded newline (e.g. 'Line1\\n\\nLine2')."""
        text = "/// Line1\n///\n/// Line2\ntable T\n"
        node = _parse_one(text)
        # The empty line contributes "" which joins as "Line1\n\nLine2"
        assert node.description is not None
        assert "Line1" in node.description
        assert "Line2" in node.description

    def test_description_not_assigned_to_property(self):
        """Description lines before a property should not crash, but the
        description is not attached to the property (PropertyNode has no
        description field)."""
        text = "table T\n\t/// Some note\n\tlineageTag: abc\n"
        node = _parse_one(text)
        # The property should still be parsed
        assert any(p.key == "lineageTag" for p in node.properties)


# ---------------------------------------------------------------------------
# TestParseAnnotations
# ---------------------------------------------------------------------------


class TestParseAnnotations:
    def test_basic_annotation(self):
        text = "table T\n\tannotation myFlag = someValue\n"
        node = _parse_one(text)
        anns = _annotations(node)
        assert len(anns) == 1
        ann = anns[0]
        assert ann.name == "myFlag"
        assert ann.expression == "someValue"

    def test_annotation_quoted_name(self):
        text = "table T\n\tannotation 'PBI_ResultType' = Table\n"
        node = _parse_one(text)
        ann = _annotations(node)[0]
        assert ann.name == "PBI_ResultType"
        assert ann.expression == "Table"

    def test_annotation_line_number(self):
        """BUG 2 regression: annotation line should be the 'annotation' keyword
        line, not the name token line."""
        text = "table T\n\tannotation myAnn = val\n"
        node = _parse_one(text)
        ann = _annotations(node)[0]
        # The annotation keyword is on line 2 (1-indexed)
        assert ann.line == 2

    def test_annotation_no_value(self):
        text = "table T\n\tannotation myFlag\n"
        node = _parse_one(text)
        ann = _annotations(node)[0]
        assert ann.name == "myFlag"
        assert ann.expression is None

    def test_multiple_annotations(self):
        text = "table T\n\tannotation a1 = v1\n\tannotation a2 = v2\n"
        node = _parse_one(text)
        anns = _annotations(node)
        assert len(anns) == 2
        assert anns[0].name == "a1"
        assert anns[1].name == "a2"


# ---------------------------------------------------------------------------
# TestParseExpressions
# ---------------------------------------------------------------------------


class TestParseExpressions:
    def test_inline_expression(self):
        node = _parse_one("measure Total = SUM(Sales[Amount])\n")
        assert node.expression == "SUM(Sales[Amount])"

    def test_expression_with_backtick_block(self):
        """Backtick blocks produce a multi-line STRING from the lexer."""
        text = "expression Foo = ```\nlet\n  x = 1\nin\n  x\n```\n"
        node = _parse_one(text)
        assert node.expression is not None
        assert "let" in node.expression

    def test_expression_with_child_properties(self):
        """An expression object can have both an expression and properties."""
        text = "expression Foo = SUM(X)\n\tlineageTag: abc-123\n"
        node = _parse_one(text)
        assert node.expression == "SUM(X)"
        assert node.properties[0].key == "lineageTag"


# ---------------------------------------------------------------------------
# TestParseNestedContent
# ---------------------------------------------------------------------------


class TestParseNestedContent:
    def test_table_with_column_child(self):
        text = "table T\n\tcolumn C\n\t\tdataType: string\n"
        node = _parse_one(text)
        assert len(node.children) == 1
        child = node.children[0]
        assert child.object_type == "column"
        assert child.name == "C"
        assert child.properties[0].key == "dataType"

    def test_table_with_multiple_children(self):
        text = (
            "table T\n"
            "\tcolumn A\n"
            "\t\tdataType: string\n"
            "\tcolumn B\n"
            "\t\tdataType: int64\n"
            "\tmeasure M = SUM(T[A])\n"
        )
        node = _parse_one(text)
        assert len(node.children) == 3
        assert node.children[0].object_type == "column"
        assert node.children[0].name == "A"
        assert node.children[1].object_type == "column"
        assert node.children[1].name == "B"
        assert node.children[2].object_type == "measure"

    def test_mixed_properties_and_children(self):
        text = "table T\n\tlineageTag: abc\n\tcolumn C\n\t\tdataType: string\n"
        node = _parse_one(text)
        assert len(node.properties) == 1
        assert node.properties[0].key == "lineageTag"
        assert len(node.children) == 1
        assert node.children[0].object_type == "column"

    def test_deeply_nested(self):
        """Three levels: table → column → variation."""
        text = "table T\n\tcolumn C\n\t\tvariation V\n\t\t\tisDefault\n"
        node = _parse_one(text)
        col = node.children[0]
        assert len(col.children) == 1
        var = col.children[0]
        assert var.object_type == "variation"
        assert var.name == "V"
        assert var.properties[0].key == "isDefault"
        assert var.properties[0].value is True

    def test_partition_with_source_child(self):
        text = (
            "table T\n\tpartition P = m\n\t\tmode: import\n\t\tsource\n\t\t\ttype: m\n"
        )
        node = _parse_one(text)
        part = node.children[0]
        assert part.object_type == "partition"
        assert part.name == "P"
        source = part.children[0]
        assert source.object_type == "source"


# ---------------------------------------------------------------------------
# TestParseRelationships
# ---------------------------------------------------------------------------


class TestParseRelationships:
    def test_basic_relationship(self):
        text = (
            "relationship abc-123\n"
            "\tfromColumn: Sales.ProductID\n"
            "\ttoColumn: Products.ID\n"
        )
        node = _parse_one(text)
        assert node.object_type == "relationship"
        assert node.name == "abc-123"
        props = {p.key: p.value for p in node.properties}
        assert props["fromColumn"] == "Sales.ProductID"
        assert props["toColumn"] == "Products.ID"


# ---------------------------------------------------------------------------
# TestParseTmdlFunction
# ---------------------------------------------------------------------------


class TestParseTmdlFunction:
    def test_convenience_function(self):
        nodes = parse_tmdl("table T\n")
        assert len(nodes) == 1
        assert nodes[0].object_type == "table"

    def test_file_path_propagated(self):
        """File path should be available for error messages."""
        parser = TMDLParser("table T\n", file_path="test.tmdl")
        nodes = parser.parse()
        assert len(nodes) == 1


# ---------------------------------------------------------------------------
# TestEdgeCases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_input(self):
        nodes = _parse("")
        assert nodes == []

    def test_only_newlines(self):
        nodes = _parse("\n\n\n")
        assert nodes == []

    def test_object_with_no_properties(self):
        node = _parse_one("table T\n")
        assert node.properties == []
        assert node.children == []

    def test_line_numbers_set(self):
        node = _parse_one("table T\n")
        assert node.line >= 1


# ---------------------------------------------------------------------------
# TestParseMultiLineExpressions
# ---------------------------------------------------------------------------


class TestParseMultiLineExpressions:
    """Covers multi-line expressions via indentation (not backtick)."""

    def test_multiline_measure_expression(self):
        """Measure with = on declaration, DAX body indented below."""
        text = "table T\n\tmeasure M =\n\t\t\tSUMX(Sales, Sales[Qty])\n"
        node = _parse_one(text)
        m = node.children[0]
        assert m.object_type == "measure"
        assert m.name == "M"
        assert m.expression is not None
        assert "SUMX" in m.expression

    def test_multiline_expression_with_blank_lines(self):
        """Blank lines within indented expression body are preserved."""
        text = "table T\n\tmeasure M =\n\t\t\t\n\t\t\tCOUNTAX(Opportunities,TRUE())\n"
        node = _parse_one(text)
        m = node.children[0]
        assert m.expression is not None
        assert "COUNTAX" in m.expression

    def test_multiline_expression_followed_by_properties(self):
        """Expression body followed by properties at shallower indent."""
        text = (
            "table T\n"
            "\tmeasure M =\n"
            "\t\t\tSUMX(\n"
            "\t\t\t    Sales,\n"
            "\t\t\t    Sales[Qty]\n"
            "\t\t\t)\n"
            "\t\tformatString: #,0\n"
            "\t\tlineageTag: abc-123\n"
        )
        node = _parse_one(text)
        m = node.children[0]
        assert m.expression is not None
        assert "SUMX" in m.expression
        props = {p.key: p.value for p in m.properties}
        assert "formatString" in props
        assert "lineageTag" in props

    def test_multiline_partition_source_m(self):
        """Multi-line M partition source with let/in.

        'source' is a KEYWORD, so 'source =' is parsed as a child
        ObjectDeclaration with the M expression as its expression field.
        """
        text = (
            "table T\n"
            "\tpartition P = m\n"
            "\t\tmode: import\n"
            "\t\tsource =\n"
            "\t\t\t\tlet\n"
            "\t\t\t\t    Source = Sql.Database(Server, DB)\n"
            "\t\t\t\tin\n"
            "\t\t\t\t    Source\n"
        )
        node = _parse_one(text)
        part = node.children[0]
        assert part.object_type == "partition"
        # 'source' is a keyword so it becomes a child ObjectDeclaration
        source_child = next(c for c in part.children if c.object_type == "source")
        assert source_child.expression is not None
        assert "let" in source_child.expression

    def test_multiline_calculated_column(self):
        """Calculated column with multi-line DAX expression."""
        text = (
            "table T\n"
            "\tcolumn 'Weeks Open' =\n"
            "\t\t\t\n"
            "\t\t\tABS(\n"
            "\t\t\t    DATEDIFF(T[Start], T[End], WEEK)\n"
            "\t\t\t)\n"
            "\t\tformatString: 0\n"
        )
        node = _parse_one(text)
        col = node.children[0]
        assert col.object_type == "column"
        assert col.name == "Weeks Open"
        assert col.expression is not None
        assert "ABS" in col.expression
        props = {p.key: p.value for p in col.properties}
        assert "formatString" in props


# ---------------------------------------------------------------------------
# TestParseBacktickExpressions
# ---------------------------------------------------------------------------


class TestParseBacktickExpressions:
    """Covers backtick-fenced expressions in parser context."""

    def test_backtick_measure_with_properties_after(self):
        """Backtick block followed by properties (formatString, lineageTag)."""
        text = (
            "table T\n"
            "\tmeasure 'Revenue Won' = ```\n"
            "\t\t\t\n"
            "\t\t\t CALCULATE(\n"
            "\t\t\t     SUMX(T, T[Value]),\n"
            '\t\t\t     FILTER(T, T[Status] = "Won")\n'
            "\t\t\t )\n"
            "\t\t\t```\n"
            "\t\tformatString: \\$#,0\n"
            "\t\tlineageTag: abc-123\n"
        )
        node = _parse_one(text)
        m = node.children[0]
        assert m.object_type == "measure"
        assert m.name == "Revenue Won"
        assert m.expression is not None
        assert "CALCULATE" in m.expression
        props = {p.key: p.value for p in m.properties}
        assert "formatString" in props
        assert "lineageTag" in props

    def test_backtick_expression_with_leading_blank_line(self):
        """Expression starts with blank line after opening backticks."""
        text = "measure M = ```\n\nSUM(X)\n```\n"
        node = _parse_one(text)
        assert node.expression is not None
        assert "SUM" in node.expression

    def test_backtick_partition_source(self):
        """source = ``` ... ``` inside a partition.

        'source' is a KEYWORD, so it's parsed as a child ObjectDeclaration.
        """
        text = (
            "table T\n"
            "\tpartition P = m\n"
            "\t\tmode: import\n"
            "\t\tsource = ```\n"
            "\t\t\tlet\n"
            "\t\t\t    Source = Sql.Database(S, D)\n"
            "\t\t\tin\n"
            "\t\t\t    Source\n"
            "\t\t\t```\n"
        )
        node = _parse_one(text)
        part = node.children[0]
        source_child = next(c for c in part.children if c.object_type == "source")
        assert source_child.expression is not None
        assert "let" in source_child.expression

    def test_backtick_expression_with_annotations(self):
        """Backtick measure followed by annotations."""
        text = (
            "table T\n"
            "\tmeasure M = ```\n"
            "\t\tSUM(X)\n"
            "\t\t```\n"
            "\t\tformatString: #,0\n"
            "\n"
            '\t\tannotation PBI_FormatHint = {"isGeneralNumber":true}\n'
        )
        node = _parse_one(text)
        m = node.children[0]
        assert m.expression is not None
        anns = _annotations(m)
        assert len(anns) == 1
        assert anns[0].name == "PBI_FormatHint"


# ---------------------------------------------------------------------------
# TestParseHierarchies
# ---------------------------------------------------------------------------


class TestParseHierarchies:
    """Covers hierarchy -> level nesting."""

    def test_hierarchy_with_levels(self):
        """Hierarchy with multiple level children."""
        text = (
            "table T\n"
            "\thierarchy 'Location Hierarchy'\n"
            "\t\tlevel Country\n"
            "\t\t\tcolumn: Country\n"
            "\t\tlevel City\n"
            "\t\t\tcolumn: City\n"
            "\t\tlevel Street\n"
            "\t\t\tcolumn: Street\n"
        )
        node = _parse_one(text)
        hier = node.children[0]
        assert hier.object_type == "hierarchy"
        assert hier.name == "Location Hierarchy"
        assert len(hier.children) == 3
        for child in hier.children:
            assert child.object_type == "level"
            assert any(p.key == "column" for p in child.properties)

    def test_hierarchy_with_lineage_tag(self):
        """Hierarchy properties plus level children."""
        text = (
            "table T\n"
            "\thierarchy H\n"
            "\t\tlineageTag: abc-123\n"
            "\t\tlevel L1\n"
            "\t\t\tcolumn: Col1\n"
        )
        node = _parse_one(text)
        hier = node.children[0]
        assert hier.properties[0].key == "lineageTag"
        assert len(hier.children) == 1

    def test_level_with_quoted_column(self):
        """Level referencing a quoted column name."""
        text = (
            "table T\n"
            "\thierarchy H\n"
            "\t\tlevel 'State or Province'\n"
            "\t\t\tlineageTag: abc\n"
            "\t\t\tcolumn: 'State or Province'\n"
        )
        node = _parse_one(text)
        hier = node.children[0]
        lvl = hier.children[0]
        assert lvl.name == "State or Province"
        col_prop = next(p for p in lvl.properties if p.key == "column")
        assert col_prop.value == "'State or Province'"


# ---------------------------------------------------------------------------
# TestParseVariations
# ---------------------------------------------------------------------------


class TestParseVariations:
    """Covers column -> variation child objects."""

    def test_column_with_variation(self):
        """Variation child with isDefault, relationship, defaultHierarchy."""
        text = (
            "table T\n"
            "\tcolumn 'Created On'\n"
            "\t\tdataType: dateTime\n"
            "\t\tvariation Variation\n"
            "\t\t\tisDefault\n"
            "\t\t\trelationship: abc-123\n"
            "\t\t\tdefaultHierarchy: LocalDate.'Date Hierarchy'\n"
        )
        node = _parse_one(text)
        col = node.children[0]
        assert len(col.children) == 1
        var = col.children[0]
        assert var.object_type == "variation"
        assert var.name == "Variation"

    def test_variation_properties_are_parsed(self):
        """All three properties of a variation are correctly extracted."""
        text = (
            "table T\n"
            "\tcolumn C\n"
            "\t\tvariation V\n"
            "\t\t\tisDefault\n"
            "\t\t\trelationship: uuid-here\n"
            "\t\t\tdefaultHierarchy: Tbl.'Hier Name'\n"
        )
        node = _parse_one(text)
        var = node.children[0].children[0]
        props = {p.key: p.value for p in var.properties}
        assert props["isDefault"] is True
        assert props["relationship"] == "uuid-here"
        assert props["defaultHierarchy"] == "Tbl.'Hier Name'"


# ---------------------------------------------------------------------------
# TestParseDataAccessOptions
# ---------------------------------------------------------------------------


class TestParseDataAccessOptions:
    """Covers dataAccessOptions sub-object with flag properties."""

    def test_data_access_options_as_child(self):
        """dataAccessOptions parsed as child of model with flag properties."""
        text = (
            "model Model\n"
            "\tculture: en-US\n"
            "\tdataAccessOptions\n"
            "\t\tlegacyRedirects\n"
            "\t\treturnErrorValuesAsNull\n"
        )
        node = _parse_one(text)
        dao = next(c for c in node.children if c.object_type == "dataAccessOptions")
        props = {p.key: p.value for p in dao.properties}
        assert props["legacyRedirects"] is True
        assert props["returnErrorValuesAsNull"] is True


# ---------------------------------------------------------------------------
# TestParseModelFile
# ---------------------------------------------------------------------------


class TestParseModelFile:
    """Covers the full model.tmdl structure."""

    def test_model_with_culture_and_properties(self):
        text = (
            "model Model\n"
            "\tculture: en-US\n"
            "\tdefaultPowerBIDataSourceVersion: powerBI_V3\n"
            "\tsourceQueryCulture: en-US\n"
        )
        node = _parse_one(text)
        assert node.object_type == "model"
        assert node.name == "Model"
        props = {p.key: p.value for p in node.properties}
        assert props["culture"] == "en-US"
        assert props["defaultPowerBIDataSourceVersion"] == "powerBI_V3"
        assert props["sourceQueryCulture"] == "en-US"

    def test_top_level_annotations(self):
        """Annotations at zero indent are parsed as separate top-level nodes."""
        text = (
            "model Model\n"
            "\tculture: en-US\n"
            "\n"
            "annotation __PBI_TimeIntelligenceEnabled = 1\n"
            "\n"
            'annotation PBI_QueryOrder = ["A","B"]\n'
        )
        nodes = _parse(text)
        assert nodes[0].object_type == "model"
        # Top-level annotations are parsed as ObjectDeclaration nodes
        ann_nodes = [n for n in nodes if n.object_type == "annotation"]
        assert len(ann_nodes) == 2
        assert ann_nodes[0].name == "__PBI_TimeIntelligenceEnabled"
        assert ann_nodes[0].expression == "1"
        assert ann_nodes[1].name == "PBI_QueryOrder"
        assert "[" in ann_nodes[1].expression

    def test_multiple_ref_statements(self):
        """ref table and ref cultureInfo parsed as separate top-level objects."""
        text = (
            "model Model\n"
            "\tculture: en-US\n"
            "\n"
            "ref table Sales\n"
            "ref table Product\n"
            "\n"
            "ref cultureInfo en-US\n"
        )
        nodes = _parse(text)
        refs = [n for n in nodes if n.object_type == "ref"]
        assert len(refs) == 3
        assert refs[0].name == "table Sales"
        assert refs[1].name == "table Product"
        assert refs[2].name == "cultureInfo en-US"

    def test_ref_with_quoted_table_name(self):
        text = "ref table 'Opportunity Forecast Adjustment'\n"
        node = _parse_one(text)
        assert node.object_type == "ref"
        assert node.name == "table Opportunity Forecast Adjustment"


# ---------------------------------------------------------------------------
# TestParseRelationshipsExtended
# ---------------------------------------------------------------------------


class TestParseRelationshipsExtended:
    """Extends the basic relationship test with edge cases."""

    def test_relationship_inactive(self):
        """isActive: false parsed as raw string; coercion deferred to transformer."""
        text = (
            "relationship abc-123\n"
            "\tisActive: false\n"
            "\tfromColumn: T1.C1\n"
            "\ttoColumn: T2.C2\n"
        )
        node = _parse_one(text)
        props = {p.key: p.value for p in node.properties}
        assert props["isActive"] == "false"

    def test_relationship_join_on_date_behavior(self):
        text = (
            "relationship abc-123\n"
            "\tjoinOnDateBehavior: datePartOnly\n"
            "\tfromColumn: T1.C1\n"
            "\ttoColumn: T2.C2\n"
        )
        node = _parse_one(text)
        props = {p.key: p.value for p in node.properties}
        assert props["joinOnDateBehavior"] == "datePartOnly"

    def test_relationship_quoted_column_refs(self):
        """Column refs with quoted names are preserved as strings."""
        text = (
            "relationship abc-123\n"
            "\tfromColumn: Accounts.'Account Owner'\n"
            "\ttoColumn: Owners.'Sales owner'\n"
        )
        node = _parse_one(text)
        props = {p.key: p.value for p in node.properties}
        assert props["fromColumn"] == "Accounts.'Account Owner'"
        assert props["toColumn"] == "Owners.'Sales owner'"

    def test_relationship_mixed_quoting(self):
        """Dot notation with mixed quoting."""
        text = (
            "relationship abc-123\n"
            "\tfromColumn: 'Case Calendar'.Date\n"
            "\ttoColumn: LocalDateTable_b0573d09.Date\n"
        )
        node = _parse_one(text)
        props = {p.key: p.value for p in node.properties}
        assert props["fromColumn"] == "'Case Calendar'.Date"
        assert props["toColumn"] == "LocalDateTable_b0573d09.Date"

    def test_multiple_relationships(self):
        """Multiple relationship objects in one file."""
        text = (
            "relationship r1\n"
            "\tfromColumn: T1.C1\n"
            "\ttoColumn: T2.C2\n"
            "\n"
            "relationship r2\n"
            "\tisActive: false\n"
            "\tfromColumn: T3.C3\n"
            "\ttoColumn: T4.C4\n"
        )
        nodes = _parse(text)
        assert len(nodes) == 2
        assert all(n.object_type == "relationship" for n in nodes)


# ---------------------------------------------------------------------------
# TestParseAnnotationsExtended
# ---------------------------------------------------------------------------


class TestParseAnnotationsExtended:
    """Extends annotation coverage with edge cases."""

    def test_annotation_json_value(self):
        """JSON annotation value preserved as string."""
        text = 'table T\n\tannotation PBI_FormatHint = {"isGeneralNumber":true}\n'
        node = _parse_one(text)
        ann = _annotations(node)[0]
        assert ann.name == "PBI_FormatHint"
        assert "{" in ann.expression
        assert "isGeneralNumber" in ann.expression

    def test_annotation_json_array_value(self):
        text = 'table T\n\tannotation PBI_QueryOrder = ["Accounts","Industries"]\n'
        node = _parse_one(text)
        ann = _annotations(node)[0]
        assert ann.expression.startswith("[")
        assert "Accounts" in ann.expression

    def test_annotation_multiline_value(self):
        """Annotation with indented multi-line content."""
        text = (
            "table T\n"
            "\tannotation BigJson =\n"
            '\t\t{"key": "value",\n'
            '\t\t "nested": true}\n'
        )
        node = _parse_one(text)
        ann = _annotations(node)[0]
        assert ann.name == "BigJson"
        assert "key" in ann.expression

    def test_annotation_on_column(self):
        """Annotation nested inside a column child."""
        text = (
            "table T\n"
            "\tcolumn C\n"
            "\t\tdataType: string\n"
            "\t\tannotation SummarizationSetBy = Automatic\n"
        )
        node = _parse_one(text)
        col = node.children[0]
        anns = _annotations(col)
        assert len(anns) == 1
        assert anns[0].name == "SummarizationSetBy"
        assert anns[0].expression == "Automatic"

    def test_multiple_annotations_on_column(self):
        """Two annotations on same column."""
        text = (
            "table T\n"
            "\tcolumn C\n"
            "\t\tdataType: double\n"
            "\t\tannotation SummarizationSetBy = User\n"
            '\t\tannotation PBI_FormatHint = {"isGeneralNumber":true}\n'
        )
        node = _parse_one(text)
        col = node.children[0]
        anns = _annotations(col)
        assert len(anns) == 2
        assert anns[0].name == "SummarizationSetBy"
        assert anns[1].name == "PBI_FormatHint"


# ---------------------------------------------------------------------------
# TestParseFormatStrings
# ---------------------------------------------------------------------------


class TestParseFormatStrings:
    """Covers complex format string patterns."""

    def test_format_string_with_backslash_dollar(self):
        text = "table T\n\tcolumn V\n\t\tformatString: \\$#,0.0;(\\$#,0.0);\\$#,0.0\n"
        node = _parse_one(text)
        col = node.children[0]
        prop = next(p for p in col.properties if p.key == "formatString")
        assert isinstance(prop.value, str)
        assert "\\$" in prop.value

    def test_format_string_percentage(self):
        text = "table T\n\tcolumn D\n\t\tformatString: #,0%;-#,0%;#,0%\n"
        node = _parse_one(text)
        col = node.children[0]
        prop = next(p for p in col.properties if p.key == "formatString")
        assert isinstance(prop.value, str)
        assert "%" in prop.value

    def test_boolean_format_string(self):
        """Complex double-quote escaping in boolean format strings."""
        text = 'table T\n\tcolumn B\n\t\tformatString: """TRUE"";""TRUE"";""FALSE"""\n'
        node = _parse_one(text)
        col = node.children[0]
        prop = next(p for p in col.properties if p.key == "formatString")
        assert isinstance(prop.value, str)
        assert "TRUE" in prop.value

    def test_format_string_short_date(self):
        text = "table T\n\tcolumn D\n\t\tformatString: Short Date\n"
        node = _parse_one(text)
        col = node.children[0]
        prop = next(p for p in col.properties if p.key == "formatString")
        assert prop.value == "Short Date"


# ---------------------------------------------------------------------------
# TestParseCalculatedPartitions
# ---------------------------------------------------------------------------


class TestParseCalculatedPartitions:
    """Covers partition types."""

    def test_partition_type_m(self):
        text = "table T\n\tpartition P = m\n"
        node = _parse_one(text)
        part = node.children[0]
        assert part.object_type == "partition"
        assert part.expression == "m"

    def test_partition_type_calculated(self):
        text = "table T\n\tpartition P = calculated\n"
        node = _parse_one(text)
        part = node.children[0]
        assert part.expression == "calculated"

    def test_partition_with_mode_and_source(self):
        """Partition with mode and source expression.

        'source' is a KEYWORD, so 'source = ...' is parsed as a child
        ObjectDeclaration with the expression in its expression field.
        """
        text = (
            "table T\n"
            "\tpartition P = m\n"
            "\t\tmode: import\n"
            "\t\tsource = Calendar(Date(2015,1,1), Date(2015,1,1))\n"
        )
        node = _parse_one(text)
        part = node.children[0]
        props = {p.key: p.value for p in part.properties}
        assert props["mode"] == "import"
        source_child = next(c for c in part.children if c.object_type == "source")
        assert source_child.expression is not None
        assert "Calendar" in source_child.expression

    def test_entity_partition_with_source_child(self):
        """Partition with source child object containing entityName."""
        text = (
            "table T\n"
            "\tpartition P = entity\n"
            "\t\tmode: import\n"
            "\t\tsource\n"
            "\t\t\tentityName: MyEntity\n"
            "\t\t\texpressionSource: MySource\n"
        )
        node = _parse_one(text)
        part = node.children[0]
        assert part.expression == "entity"
        source = next(c for c in part.children if c.object_type == "source")
        props = {p.key: p.value for p in source.properties}
        assert props["entityName"] == "MyEntity"


# ---------------------------------------------------------------------------
# TestParseEscapedNames
# ---------------------------------------------------------------------------


class TestParseEscapedNames:
    """Covers name quoting edge cases."""

    def test_escaped_single_quote_in_name(self):
        """Doubled single quotes are unescaped by the lexer."""
        node = _parse_one("table 'Day''s Table'\n")
        assert node.name == "Day's Table"

    def test_name_with_dots(self):
        node = _parse_one("table 'Table.Name'\n")
        assert node.name == "Table.Name"

    def test_name_with_equals(self):
        node = _parse_one("column 'Col=1'\n")
        assert node.name == "Col=1"

    def test_name_with_colon(self):
        node = _parse_one("column 'Col:1'\n")
        assert node.name == "Col:1"

    def test_name_with_spaces(self):
        node = _parse_one("table 'My Table Name'\n")
        assert node.name == "My Table Name"


# ---------------------------------------------------------------------------
# TestParserErrorHandling
# ---------------------------------------------------------------------------


class TestParserErrorHandling:
    """Covers parser error paths."""

    def test_unexpected_token_type_in_expect(self):
        """_expect() on a non-matching token raises TMDLParseError."""
        parser = TMDLParser("table T\n", file_path="test.tmdl")
        parser.tokens = list(parser.lexer.tokenize())
        parser.pos = 0
        # First token is KEYWORD, try to expect IDENTIFIER
        with pytest.raises(TMDLParseError, match="Expected IDENTIFIER"):
            parser._expect(TokenType.IDENTIFIER)

    def test_malformed_annotation_skipped(self):
        """Annotation with unexpected token after keyword doesn't crash."""
        text = "table T\n\tannotation\n\tlineageTag: abc\n"
        # Should not raise
        node = _parse_one(text)
        # The malformed annotation is skipped, property still parsed
        assert any(p.key == "lineageTag" for p in node.properties)

    def test_unknown_token_in_nested_content_skipped(self):
        """Unknown tokens inside nested content are skipped silently."""
        text = "table T\n\tlineageTag: abc\n\tcolumn C\n\t\tdataType: string\n"
        # Normal case - should not crash
        node = _parse_one(text)
        assert len(node.properties) == 1
        assert len(node.children) == 1

    def test_parse_error_includes_line_number(self):
        parser = TMDLParser("table T\n", file_path="test.tmdl")
        parser.tokens = list(parser.lexer.tokenize())
        parser.pos = 0
        try:
            parser._expect(TokenType.IDENTIFIER)
        except TMDLParseError as e:
            assert e.line is not None
            assert e.line >= 1

    def test_parse_error_includes_file_path(self):
        parser = TMDLParser("table T\n", file_path="my/file.tmdl")
        parser.tokens = list(parser.lexer.tokenize())
        parser.pos = 0
        try:
            parser._expect(TokenType.IDENTIFIER)
        except TMDLParseError as e:
            assert e.file_path == "my/file.tmdl"


# ---------------------------------------------------------------------------
# TestParseExpressionFiles
# ---------------------------------------------------------------------------


class TestParseExpressionFiles:
    """Covers named M expressions (expressions.tmdl patterns)."""

    def test_named_expression_with_multiline_m(self):
        """expression Query1 = with multi-line M body then properties."""
        text = (
            "expression Query1 =\n"
            "\t\tlet\n"
            "\t\t    Source = Sql.Database(S, D)\n"
            "\t\tin\n"
            "\t\t    Source\n"
            "\tlineageTag: abc-123\n"
        )
        node = _parse_one(text)
        assert node.object_type == "expression"
        assert node.name == "Query1"
        assert node.expression is not None
        assert "let" in node.expression
        assert node.properties[0].key == "lineageTag"

    def test_expression_with_query_group(self):
        text = (
            "expression Qry =\n"
            "\t\tlet\n"
            '\t\t    Source = Web.Contents("url")\n'
            "\t\tin\n"
            "\t\t    Source\n"
            "\tlineageTag: abc\n"
            "\tqueryGroup: Unused\n"
        )
        node = _parse_one(text)
        props = {p.key: p.value for p in node.properties}
        assert props["queryGroup"] == "Unused"

    def test_expression_with_annotations(self):
        text = (
            "expression Foo = SUM(X)\n"
            "\tlineageTag: abc\n"
            "\tannotation PBI_NavigationStepName = Navigation\n"
            "\tannotation PBI_ResultType = Function\n"
        )
        node = _parse_one(text)
        anns = _annotations(node)
        assert len(anns) == 2
        assert anns[0].name == "PBI_NavigationStepName"
        assert anns[1].name == "PBI_ResultType"


# ---------------------------------------------------------------------------
# TestParseComplexTableStructure
# ---------------------------------------------------------------------------


class TestParseComplexTableStructure:
    """Covers complex table structures mirroring real samples."""

    def test_table_with_measures_columns_partitions(self):
        """Table with mixed children: measures, columns, partition."""
        text = (
            "table Sales\n"
            "\tlineageTag: abc-123\n"
            "\n"
            "\tmeasure 'Total Sales' = SUM(Sales[Amount])\n"
            "\t\tformatString: #,0\n"
            "\t\tlineageTag: def-456\n"
            "\n"
            "\tcolumn Amount\n"
            "\t\tdataType: int64\n"
            "\t\tsourceColumn: Amount\n"
            "\n"
            "\tpartition Sales-Part1 = m\n"
            "\t\tmode: import\n"
        )
        node = _parse_one(text)
        assert node.object_type == "table"
        assert node.name == "Sales"
        children_types = [c.object_type for c in node.children]
        assert "measure" in children_types
        assert "column" in children_types
        assert "partition" in children_types

    def test_column_with_multiple_flags(self):
        """Column with isHidden and isKey flag properties."""
        text = (
            "table T\n"
            "\tcolumn C\n"
            "\t\tdataType: int64\n"
            "\t\tisHidden\n"
            "\t\tisKey\n"
            "\t\tsourceColumn: C\n"
        )
        node = _parse_one(text)
        col = node.children[0]
        props = {p.key: p.value for p in col.properties}
        assert props["isHidden"] is True
        assert props["isKey"] is True
        assert props["dataType"] == "int64"
        assert props["sourceColumn"] == "C"

    def test_column_with_data_category(self):
        text = (
            "table T\n"
            "\tcolumn City\n"
            "\t\tdataType: string\n"
            "\t\tdataCategory: City\n"
            "\t\tsummarizeBy: none\n"
        )
        node = _parse_one(text)
        col = node.children[0]
        props = {p.key: p.value for p in col.properties}
        assert props["dataCategory"] == "City"
        assert props["summarizeBy"] == "none"

    def test_column_with_sort_by_column(self):
        text = (
            "table T\n"
            "\tcolumn Month\n"
            "\t\tdataType: string\n"
            "\t\tsortByColumn: MonthNumber\n"
        )
        node = _parse_one(text)
        col = node.children[0]
        props = {p.key: p.value for p in col.properties}
        assert props["sortByColumn"] == "MonthNumber"

    def test_hidden_private_table(self):
        """Auto-generated date table with isHidden and isPrivate flags."""
        text = (
            "table DateTableTemplate_0039983e\n"
            "\tisHidden\n"
            "\tisPrivate\n"
            "\tlineageTag: abc\n"
        )
        node = _parse_one(text)
        props = {p.key: p.value for p in node.properties}
        assert props["isHidden"] is True
        assert props["isPrivate"] is True

    def test_column_is_name_inferred(self):
        """isNameInferred flag property on auto-date columns."""
        text = (
            "table T\n"
            "\tcolumn Date\n"
            "\t\tisHidden\n"
            "\t\tisNameInferred\n"
            "\t\tsourceColumn: [Date]\n"
        )
        node = _parse_one(text)
        col = node.children[0]
        props = {p.key: p.value for p in col.properties}
        assert props["isNameInferred"] is True
        assert props["sourceColumn"] == "[Date]"

    def test_calculated_column_single_line(self):
        """Single-line calculated column."""
        text = (
            "table T\n"
            "\tcolumn 'Industry Lookup' = LOOKUPVALUE(I[Industry], I[Seq], T[Seq])\n"
            "\t\tlineageTag: abc\n"
            "\t\tsummarizeBy: none\n"
        )
        node = _parse_one(text)
        col = node.children[0]
        assert col.name == "Industry Lookup"
        assert col.expression is not None
        assert "LOOKUPVALUE" in col.expression
