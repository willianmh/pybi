import pytest

from pybi.semanticmodel import (
    Column,
    Measure,
    Relationship,
    SemanticModel,
    Table,
    SemanticModelDefinition,
    Model,
)
from pybi.serialization import deserialize, serialize


def _build_small_model() -> SemanticModelDefinition:
    """Build a small semantic model: 1 table, 5 columns, 2 measures."""
    columns = [
        Column(name="SalesDate", dataType="dateTime", summarizeBy="none"),
        Column(
            name="Amount",
            dataType="decimal",
            formatString="$ #,##0.00",
            summarizeBy="sum",
        ),
        Column(name="ProductKey", dataType="int64", isKey=True, summarizeBy="none"),
        Column(name="CustomerKey", dataType="int64", summarizeBy="none"),
        Column(name="Quantity", dataType="int64", summarizeBy="sum"),
    ]
    measures = [
        Measure(
            name="Total Sales",
            expression="SUM(Sales[Amount])",
            formatString="$ #,##0.00",
            displayFolder="Key Metrics",
        ),
        Measure(
            name="Total Quantity",
            expression="SUM(Sales[Quantity])",
            formatString="#,##0",
            displayFolder="Key Metrics",
        ),
    ]
    table = Table(name="Sales", columns=columns, measures=measures)
    model = Model(culture="en-US", tables=[table])

    return SemanticModelDefinition(model=model)


def _build_large_model() -> SemanticModelDefinition:
    """Build a large semantic model: 10 tables, 10 columns + 5 measures each."""
    tables = []
    for t in range(10):
        columns = [
            Column(
                name=f"Column{c}",
                dataType="string" if c % 3 != 0 else "int64",
                isKey=(c == 0),
                summarizeBy="none" if c % 2 == 0 else "sum",
            )
            for c in range(10)
        ]
        measures = [
            Measure(
                name=f"Measure{m}",
                expression=f"SUM(Table{t}[Column{m}])",
                displayFolder="Metrics",
            )
            for m in range(5)
        ]
        tables.append(Table(name=f"Table{t}", columns=columns, measures=measures))

    relationships = [
        Relationship(
            name=f"Table0_Table{t}",
            fromTable="Table0",
            fromColumn="Column0",
            toTable=f"Table{t}",
            toColumn="Column0",
        )
        for t in range(1, 10)
    ]

    model = Model(culture="en-US", tables=tables, relationships=relationships)

    return SemanticModelDefinition(model=model)


_SMALL_MODEL = _build_small_model()
_LARGE_MODEL = _build_large_model()
_SMALL_JSON = serialize(_SMALL_MODEL)
_LARGE_JSON = serialize(_LARGE_MODEL)


def test_serialize_small_model(benchmark) -> None:
    """Benchmark serializing a small semantic model to JSON."""
    benchmark(serialize, _SMALL_MODEL)


def test_serialize_large_model(benchmark) -> None:
    """Benchmark serializing a large semantic model to JSON."""
    benchmark(serialize, _LARGE_MODEL)


def test_deserialize_small_model(benchmark) -> None:
    """Benchmark deserializing a small semantic model from JSON."""
    benchmark(deserialize, SemanticModelDefinition, _SMALL_JSON)


def test_deserialize_large_model(benchmark) -> None:
    """Benchmark deserializing a large semantic model from JSON."""
    benchmark(deserialize, SemanticModelDefinition, _LARGE_JSON)
