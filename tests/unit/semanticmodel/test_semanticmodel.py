import pytest

from pybi.collections import NamedList
from pybi.errors import (
    AmbiguousMeasureError,
    ColumnNotFoundError,
    DuplicateNameError,
    MeasureNotFoundError,
    TableNotFoundError,
)
from pybi.fabric.fabric import DefinitionPbism, Metadata, Platform
from pybi.semanticmodel.definition import (
    Column,
    ExpressionValue,
    Measure,
    SemanticModelDefinition,
    Table,
)
from pybi.semanticmodel.semanticmodel import SemanticModel


SM = {
    "compatibilityLevel": 1567,
    "model": {
        "culture": "en-US",
        "defaultPowerBIDataSourceVersion": "powerBI_V3",
        "expressions": [
            {
                "name": "Query1",
                "expression": ["..."],
                "kind": "m",
                "lineageTag": "2ddf0ecd-db05-43f2-99eb-bfc444d25f5d",
            }
        ],
        "relationships": [
            {
                "name": "89a44a58-1397-4839-a0fe-c46c0c5d890d",
                "fromColumn": "Column1",
                "fromTable": "Table1",
                "toColumn": "Column1",
                "toTable": "Table2",
            }
        ],
        "sourceQueryCulture": "en-US",
        "tables": [
            {
                "name": "Table1",
                "columns": [
                    {
                        "name": "Column1",
                        "dataType": "string",
                        "lineageTag": "3cc966b9-42cc-4fdc-af3e-169dbd480556",
                        "sourceColumn": "Column1",
                        "summarizeBy": "none",
                    },
                    {
                        "name": "Column2",
                        "dataType": "string",
                        "lineageTag": "ed257708-4559-4704-a277-a67e5437a1ca",
                        "sourceColumn": "Column2",
                        "summarizeBy": "none",
                    },
                ],
                "lineageTag": "22d72ed3-5ee0-4ff1-98ec-c82153839a11",
                "partitions": [
                    {
                        "name": "Table1-569e2118-8ef4-4f17-9647-c9b4190bc0c8",
                        "mode": "import",
                        "source": {"expression": ["..."], "type": "m"},
                    }
                ],
            },
            {
                "name": "Table2",
                "columns": [
                    {
                        "name": "Column1",
                        "dataType": "string",
                        "lineageTag": "8b10b876-f44a-4959-846f-ddd0db70c358",
                        "sourceColumn": "Column1",
                        "summarizeBy": "none",
                    },
                    {
                        "name": "Column2",
                        "dataType": "int64",
                        "formatString": "0",
                        "lineageTag": "2b094873-0bc1-4789-8a16-fe25ba521900",
                        "sourceColumn": "Column2",
                        "summarizeBy": "none",
                    },
                ],
                "lineageTag": "46e20580-f584-47f3-9fb6-650aaf55c07d",
                "partitions": [
                    {
                        "name": "Table2-ad0b018f-e5af-41ce-a3f4-c734e885246e",
                        "mode": "import",
                        "source": {"expression": ["..."], "type": "m"},
                    }
                ],
            },
        ],
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_sm(definition_dict: dict | None = None) -> SemanticModel:
    """Build a minimal SemanticModel from a definition dict (defaults to SM)."""
    return SemanticModel(
        item_definition=DefinitionPbism(),
        definition=SemanticModelDefinition.model_validate(
            definition_dict if definition_dict is not None else SM
        ),
        platform=Platform(
            metadata=Metadata(type="SemanticModel", displayName="Test Model")
        ),
    )


def make_measure(name: str) -> Measure:
    return Measure(name=name, expression="1")


def make_column(name: str) -> Column:
    return Column(name=name, dataType="string")


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------


class TestProperties:
    def test_tables_returns_named_list(self):
        sm = make_sm()
        assert isinstance(sm.tables, NamedList)
        assert len(sm.tables) == 2

    def test_tables_supports_name_indexing(self):
        sm = make_sm()
        t = sm.tables["Table1"]
        assert t.name == "Table1"

    def test_tables_empty_when_none(self):
        sm = make_sm({"compatibilityLevel": 1600, "model": {}})
        assert sm.tables == []

    def test_relationships(self):
        sm = make_sm()
        assert len(sm.relationships) == 1
        assert sm.relationships[0].fromTable == "Table1"

    def test_expressions(self):
        sm = make_sm()
        assert isinstance(sm.expressions, NamedList)
        assert sm.expressions[0].name == "Query1"

    def test_columns_flat_list(self):
        sm = make_sm()
        pairs = sm.columns
        assert len(pairs) == 4  # 2 columns per table
        tables = {t.name for t, _ in pairs}
        assert tables == {"Table1", "Table2"}

    def test_measures_empty_when_no_measures(self):
        sm = make_sm()
        assert sm.measures == []

    def test_measures_flat_list(self):
        sm = make_sm()
        sm.tables["Table1"].add_measure(make_measure("Revenue"))
        sm.tables["Table2"].add_measure(make_measure("Cost"))
        pairs = sm.measures
        assert len(pairs) == 2
        measure_names = {m.name for _, m in pairs}
        assert measure_names == {"Revenue", "Cost"}


# ---------------------------------------------------------------------------
# Table lookups
# ---------------------------------------------------------------------------


class TestTableLookups:
    def test_get_table_found(self):
        sm = make_sm()
        assert sm.get_table("Table1").name == "Table1"

    def test_get_table_not_found_raises(self):
        sm = make_sm()
        with pytest.raises(TableNotFoundError) as exc:
            sm.get_table("Missing")
        assert exc.value.name == "Missing"

    def test_find_table_found(self):
        sm = make_sm()
        assert sm.find_table("Table2") is not None

    def test_find_table_not_found_returns_none(self):
        sm = make_sm()
        assert sm.find_table("Missing") is None


# ---------------------------------------------------------------------------
# Column lookups
# ---------------------------------------------------------------------------


class TestColumnLookups:
    def test_get_column_found(self):
        sm = make_sm()
        col = sm.get_column("Table1", "Column1")
        assert col.name == "Column1"

    def test_get_column_not_found_raises(self):
        sm = make_sm()
        with pytest.raises(ColumnNotFoundError) as exc:
            sm.get_column("Table1", "Missing")
        assert exc.value.name == "Missing"
        assert exc.value.table == "Table1"

    def test_get_column_table_not_found_raises(self):
        sm = make_sm()
        with pytest.raises(TableNotFoundError):
            sm.get_column("Missing", "Column1")

    def test_find_column_found(self):
        sm = make_sm()
        assert sm.find_column("Table1", "Column2") is not None

    def test_find_column_bad_column_returns_none(self):
        sm = make_sm()
        assert sm.find_column("Table1", "Missing") is None

    def test_find_column_bad_table_returns_none(self):
        sm = make_sm()
        assert sm.find_column("Missing", "Column1") is None


# ---------------------------------------------------------------------------
# Measure lookups
# ---------------------------------------------------------------------------


class TestMeasureLookups:
    def test_get_measure_found(self):
        sm = make_sm()
        sm.tables["Table1"].add_measure(make_measure("Revenue"))
        m = sm.get_measure("Revenue")
        assert m.name == "Revenue"

    def test_get_measure_scoped_to_table(self):
        sm = make_sm()
        sm.tables["Table1"].add_measure(make_measure("Revenue"))
        m = sm.get_measure("Revenue", table="Table1")
        assert m.name == "Revenue"

    def test_get_measure_not_found_raises(self):
        sm = make_sm()
        with pytest.raises(MeasureNotFoundError) as exc:
            sm.get_measure("Missing")
        assert exc.value.name == "Missing"

    def test_get_measure_not_found_scoped_raises(self):
        sm = make_sm()
        sm.tables["Table1"].add_measure(make_measure("Revenue"))
        with pytest.raises(MeasureNotFoundError) as exc:
            sm.get_measure("Revenue", table="Table2")
        assert exc.value.table == "Table2"

    def test_get_measure_ambiguous_raises(self):
        sm = make_sm()
        sm.tables["Table1"].add_measure(make_measure("Revenue"))
        sm.tables["Table2"].add_measure(make_measure("Revenue"))
        with pytest.raises(AmbiguousMeasureError) as exc:
            sm.get_measure("Revenue")
        assert set(exc.value.tables) == {"Table1", "Table2"}

    def test_find_measure_found(self):
        sm = make_sm()
        sm.tables["Table1"].add_measure(make_measure("Revenue"))
        assert sm.find_measure("Revenue") is not None

    def test_find_measure_not_found_returns_none(self):
        sm = make_sm()
        assert sm.find_measure("Missing") is None


# ---------------------------------------------------------------------------
# Mutations - SemanticModel level
# ---------------------------------------------------------------------------


class TestMutations:
    def test_add_table(self):
        sm = make_sm()
        sm.add_table(Table(name="NewTable", partitions=[]))
        assert sm.find_table("NewTable") is not None

    def test_add_table_duplicate_raises(self):
        sm = make_sm()
        with pytest.raises(DuplicateNameError):
            sm.add_table(Table(name="Table1", partitions=[]))

    def test_remove_table(self):
        sm = make_sm()
        removed = sm.remove_table("Table1")
        assert removed.name == "Table1"
        assert sm.find_table("Table1") is None

    def test_remove_table_not_found_raises(self):
        sm = make_sm()
        with pytest.raises(TableNotFoundError):
            sm.remove_table("Missing")


# ---------------------------------------------------------------------------
# Mutations - Table level (columns)
# ---------------------------------------------------------------------------


class TestTableColumnMutations:
    def test_add_column(self):
        sm = make_sm()
        t = sm.tables["Table1"]
        t.add_column(make_column("NewCol"))
        assert t.find_column("NewCol") is not None

    def test_add_column_duplicate_raises(self):
        sm = make_sm()
        t = sm.tables["Table1"]
        with pytest.raises(DuplicateNameError):
            t.add_column(make_column("Column1"))

    def test_remove_column(self):
        sm = make_sm()
        t = sm.tables["Table1"]
        removed = t.remove_column("Column1")
        assert removed.name == "Column1"
        assert t.find_column("Column1") is None

    def test_remove_column_not_found_raises(self):
        sm = make_sm()
        with pytest.raises(ColumnNotFoundError):
            sm.tables["Table1"].remove_column("Missing")


# ---------------------------------------------------------------------------
# Mutations - Table level (measures)
# ---------------------------------------------------------------------------


class TestTableMeasureMutations:
    def test_add_measure(self):
        sm = make_sm()
        t = sm.tables["Table1"]
        t.add_measure(make_measure("Revenue"))
        assert t.find_measure("Revenue") is not None

    def test_add_measure_duplicate_raises(self):
        sm = make_sm()
        t = sm.tables["Table1"]
        t.add_measure(make_measure("Revenue"))
        with pytest.raises(DuplicateNameError):
            t.add_measure(make_measure("Revenue"))

    def test_remove_measure(self):
        sm = make_sm()
        t = sm.tables["Table1"]
        t.add_measure(make_measure("Revenue"))
        removed = t.remove_measure("Revenue")
        assert removed.name == "Revenue"
        assert t.find_measure("Revenue") is None

    def test_remove_measure_not_found_raises(self):
        sm = make_sm()
        with pytest.raises(MeasureNotFoundError):
            sm.tables["Table1"].remove_measure("Missing")


# ---------------------------------------------------------------------------
# Expression field storage
# ---------------------------------------------------------------------------


class TestExpressionFieldStorage:
    """Expression fields store whatever the caller passes; no coercion."""

    def test_measure_stores_str_as_is(self):
        m = Measure(name="M", expression="SUM(Sales[Amount])")
        assert m.expression == "SUM(Sales[Amount])"
        assert isinstance(m.expression, str)

    def test_measure_stores_list_as_is(self):
        m = Measure(name="M", expression=["VAR x = 1", "RETURN x"])
        assert m.expression == ["VAR x = 1", "RETURN x"]
        assert isinstance(m.expression, list)

    def test_measure_stores_expression_value_as_is(self):
        ev = ExpressionValue(value="1+1")
        m = Measure(name="M", expression=ev)
        assert m.expression is ev

    def test_assignment_stores_raw_str(self):
        m = Measure(name="M", expression="1")
        m.expression = "2"
        assert m.expression == "2"
        assert isinstance(m.expression, str)

    def test_model_dump_str_roundtrips(self):
        m = Measure(name="M", expression="SUM(Sales[Amount])")
        dumped = m.model_dump(exclude_none=True, exclude_unset=True)
        assert dumped["expression"] == "SUM(Sales[Amount])"

    def test_model_dump_list_roundtrips(self):
        m = Measure(name="M", expression=["VAR x = 1", "RETURN x"])
        dumped = m.model_dump(exclude_none=True, exclude_unset=True)
        assert dumped["expression"] == ["VAR x = 1", "RETURN x"]

    def test_model_dump_expression_value_serialized_inline(self):
        from pybi.serialization.parsers.tmdl.grammar import ExpressionStyle

        ev = ExpressionValue(value="1+1", style=ExpressionStyle.INLINE)
        m = Measure(name="M", expression=ev)
        dumped = m.model_dump(exclude_none=True, exclude_unset=True)
        assert dumped["expression"] == "1+1"

    def test_model_dump_expression_value_serialized_multiline(self):
        from pybi.serialization.parsers.tmdl.grammar import ExpressionStyle

        ev = ExpressionValue(
            value="VAR x = 1\nRETURN x", style=ExpressionStyle.MULTILINE
        )
        m = Measure(name="M", expression=ev)
        dumped = m.model_dump(exclude_none=True, exclude_unset=True)
        assert dumped["expression"] == ["VAR x = 1", "RETURN x"]

    def test_none_expression_stored_as_none(self):
        m = Measure(name="M")
        assert m.expression is None
