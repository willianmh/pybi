"""Unit tests for the TMDL transformer (AST nodes → Pydantic models)."""

from pybi.serialization.parsers.tmdl.parser import ObjectDeclaration, PropertyNode
from pybi.serialization.parsers.tmdl.transformer import TMDLTransformer


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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestTransformDatabase:
    def test_extracts_compatibility_level(self):
        node = _node("database", properties=[_prop("compatibilityLevel", "1567")])
        t = TMDLTransformer()
        assert t.transform_database(node) == 1567

    def test_defaults_to_1600(self):
        node = _node("database")
        t = TMDLTransformer()
        assert t.transform_database(node) == 1600


class TestTransformColumn:
    def test_basic_column(self):
        node = _node(
            "column",
            name="Revenue",
            properties=[
                _prop("dataType", "double"),
                _prop("lineageTag", "abc-123"),
                _prop("sourceColumn", "Revenue"),
                _prop("summarizeBy", "sum"),
            ],
        )
        col = TMDLTransformer().transform_column(node)
        assert col.name == "Revenue"
        assert col.dataType == "double"
        assert col.lineageTag == "abc-123"
        assert col.sourceColumn == "Revenue"
        assert col.summarizeBy == "sum"

    def test_calculated_column_expression(self):
        """ObjectDeclaration.expression is correctly mapped to Column.expression."""
        node = _node(
            "column",
            name="FullName",
            expression='[FirstName] & " " & [LastName]',
            properties=[
                _prop("lineageTag", "def-456"),
            ],
        )
        col = TMDLTransformer().transform_column(node)
        assert col.name == "FullName"
        assert col.expression == '[FirstName] & " " & [LastName]'


class TestTransformMeasure:
    def test_single_line_expression(self):
        node = _node(
            "measure",
            name="Total Sales",
            expression="SUM(Sales[Amount])",
            properties=[_prop("lineageTag", "m-001")],
        )
        m = TMDLTransformer().transform_measure(node)
        assert m.name == "Total Sales"
        assert m.expression == "SUM(Sales[Amount])"

    def test_multi_line_expression(self):
        expr = "CALCULATE(\n    SUM(Sales[Amount]),\n    FILTER(Sales, Sales[Year] = 2024)\n)"
        node = _node(
            "measure",
            name="Filtered Sales",
            expression=expr,
            properties=[_prop("lineageTag", "m-002")],
        )
        m = TMDLTransformer().transform_measure(node)
        assert isinstance(m.expression, list)
        assert len(m.expression) == 4

    def test_format_string(self):
        node = _node(
            "measure",
            name="Revenue",
            expression="SUM(T[Rev])",
            properties=[
                _prop("lineageTag", "m-003"),
                _prop("formatString", "$#,0.00"),
            ],
        )
        m = TMDLTransformer().transform_measure(node)
        assert m.formatString == "$#,0.00"


class TestTransformPartition:
    def test_m_partition(self):
        source_child = _node("source", expression="m")
        node = _node(
            "partition",
            name="Sales-part",
            expression="m",
            properties=[_prop("mode", "import")],
            children=[source_child],
        )
        p = TMDLTransformer().transform_partition(node)
        assert p.name == "Sales-part"
        assert p.mode == "import"
        assert p.source.type == "m"

    def test_entity_partition(self):
        source_child = _node(
            "source",
            properties=[_prop("entityName", "DimProduct")],
        )
        node = _node(
            "partition",
            name="Products-part",
            expression="entity",
            properties=[_prop("mode", "directLake")],
            children=[source_child],
        )
        p = TMDLTransformer().transform_partition(node)
        assert p.source.type == "entity"
        assert p.source.entityName == "DimProduct"


class TestTransformRelationship:
    def test_parses_column_references(self):
        node = _node(
            "relationship",
            name="rel-001",
            properties=[
                _prop("fromColumn", "Sales.'Customer ID'"),
                _prop("toColumn", "Customers.ID"),
            ],
        )
        r = TMDLTransformer().transform_relationship(node)
        assert r.name == "rel-001"
        assert r.fromTable == "Sales"
        assert r.fromColumn == "Customer ID"
        assert r.toTable == "Customers"
        assert r.toColumn == "ID"


class TestTransformTable:
    def test_table_with_children(self):
        col = _node(
            "column",
            name="ID",
            properties=[
                _prop("dataType", "int64"),
                _prop("lineageTag", "c-001"),
                _prop("sourceColumn", "ID"),
            ],
        )
        measure = _node(
            "measure",
            name="Count",
            expression="COUNTROWS(T)",
            properties=[_prop("lineageTag", "m-001")],
        )
        source = _node("source")
        partition = _node(
            "partition",
            name="T-part",
            expression="m",
            properties=[_prop("mode", "import")],
            children=[source],
        )
        table_node = _node(
            "table",
            name="T",
            properties=[_prop("lineageTag", "t-001")],
            children=[col, measure, partition],
        )

        t = TMDLTransformer().transform_table(table_node)
        assert t.name == "T"
        assert t.lineageTag == "t-001"
        assert t.columns is not None and len(t.columns) == 1
        assert t.columns[0].name == "ID"
        assert t.measures is not None and len(t.measures) == 1
        assert t.measures[0].name == "Count"
        assert len(t.partitions) == 1


class TestTransformModel:
    def test_injects_collections(self):
        from pybi.semanticmodel.definition import (
            Column,
            Culture,
            Expression,
            Measure,
            Partition,
            Relationship,
            Source,
            Table,
        )

        model_node = _node(
            "model",
            name="Model",
            properties=[_prop("culture", "en-US")],
        )
        tables = [
            Table(
                name="T",
                lineageTag="t-1",
                partitions=[
                    Partition(name="p", mode="import", source=Source(type="m"))
                ],
            )
        ]
        relationships = [
            Relationship(
                name="r-1",
                fromColumn="A",
                fromTable="T",
                toColumn="B",
                toTable="T2",
            )
        ]
        expressions = [Expression(name="e-1", expression="let x = 1 in x")]
        cultures = [Culture(name="en-US")]

        m = TMDLTransformer().transform_model(
            model_node,
            tables=tables,
            relationships=relationships,
            expressions=expressions,
            cultures=cultures,
        )
        assert m.tables == tables
        assert m.relationships == relationships
        assert m.expressions == expressions
        assert m.cultures == cultures
        assert m.culture == "en-US"
