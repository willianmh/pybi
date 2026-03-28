"""Unit tests for the TMDL parts loader (in-memory file dict → Model)."""

import pytest

from pybi.serialization.parsers.tmdl.loader import TMDLPartsLoader


# ---------------------------------------------------------------------------
# Shared minimal TMDL content
# ---------------------------------------------------------------------------

_DATABASE = "database\n\tcompatibilityLevel: 1600\n"
_DATABASE_1567 = "database\n\tcompatibilityLevel: 1567\n"
_MODEL = "model Model\n\tculture: en-US\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLoaderMinimal:
    def test_empty_files_without_model_config(self):
        """When no model.tmdl is present, the loader falls back to direct
        Model() construction which fails because expressions (required list)
        receives None. This documents the current behavior."""
        with pytest.raises(Exception):
            TMDLPartsLoader({}).load()

    def test_database_and_model(self):
        files = {"database.tmdl": _DATABASE_1567, "model.tmdl": _MODEL}
        result = TMDLPartsLoader(files).load()
        assert result["compatibilityLevel"] == 1567
        assert result["model"] is not None
        assert result["model"].tables is None
        assert result["model"].culture == "en-US"

    def test_default_compatibility_level(self):
        files = {"model.tmdl": _MODEL}
        result = TMDLPartsLoader(files).load()
        assert result["compatibilityLevel"] == 1600


class TestLoaderComponents:
    def test_loads_tables(self):
        files = {
            "database.tmdl": _DATABASE,
            "model.tmdl": _MODEL,
            "tables/Foo.tmdl": (
                "table Foo\n"
                "\tlineageTag: abc-123\n"
                "\n"
                "\tcolumn ID\n"
                "\t\tdataType: int64\n"
                "\t\tlineageTag: col-1\n"
                "\t\tsourceColumn: ID\n"
                "\n"
                "\tpartition Foo-part = m\n"
                "\t\tmode: import\n"
                "\t\tsource =\n"
                "\t\t\tlet Source = Sql.Database() in Source\n"
            ),
        }
        result = TMDLPartsLoader(files).load()
        model = result["model"]
        assert model.tables is not None
        assert len(model.tables) == 1
        assert model.tables[0].name == "Foo"
        assert model.tables[0].columns is not None
        assert model.tables[0].columns[0].name == "ID"

    def test_loads_relationships(self):
        files = {
            "database.tmdl": _DATABASE,
            "model.tmdl": _MODEL,
            "relationships.tmdl": (
                "relationship r1\n"
                "\tfromColumn: Sales.CustomerID\n"
                "\ttoColumn: Customers.ID\n"
            ),
        }
        result = TMDLPartsLoader(files).load()
        model = result["model"]
        assert model.relationships is not None
        assert len(model.relationships) == 1
        rel = model.relationships[0]
        assert rel.fromTable == "Sales"
        assert rel.fromColumn == "CustomerID"
        assert rel.toTable == "Customers"
        assert rel.toColumn == "ID"

    def test_loads_expressions(self):
        files = {
            "database.tmdl": _DATABASE,
            "model.tmdl": _MODEL,
            "expressions.tmdl": (
                "expression MySource = let x = 1 in x\n"
                "\tlineageTag: expr-1\n"
            ),
        }
        result = TMDLPartsLoader(files).load()
        model = result["model"]
        assert len(model.expressions) == 1
        assert model.expressions[0].name == "MySource"

    def test_loads_cultures(self):
        files = {
            "database.tmdl": _DATABASE,
            "model.tmdl": _MODEL,
            "cultures/en-US.tmdl": (
                "cultureInfo en-US\n"
                '\n'
                '\tlinguisticMetadata =\n'
                '\t\t\t{\n'
                '\t\t\t  "Language": "en-US",\n'
                '\t\t\t  "Version": "1.0.0"\n'
                '\t\t\t}\n'
                '\t\tcontentType: json\n'
            ),
        }
        result = TMDLPartsLoader(files).load()
        model = result["model"]
        assert len(model.cultures) == 1
        assert model.cultures[0].name == "en-US"

    def test_default_culture_when_none(self):
        files = {"database.tmdl": _DATABASE, "model.tmdl": _MODEL}
        result = TMDLPartsLoader(files).load()
        model = result["model"]
        assert len(model.cultures) == 1
        assert model.cultures[0].name == "en-US"

    def test_multiple_tables(self):
        files = {
            "database.tmdl": _DATABASE,
            "model.tmdl": _MODEL,
            "tables/A.tmdl": (
                "table A\n"
                "\tlineageTag: a-1\n"
                "\n"
                "\tpartition A-p = m\n"
                "\t\tmode: import\n"
            ),
            "tables/B.tmdl": (
                "table B\n"
                "\tlineageTag: b-1\n"
                "\n"
                "\tpartition B-p = m\n"
                "\t\tmode: import\n"
            ),
        }
        result = TMDLPartsLoader(files).load()
        model = result["model"]
        assert model.tables is not None
        names = {t.name for t in model.tables}
        assert names == {"A", "B"}
