"""Performance benchmarks for pybi serialization and deserialization."""

from __future__ import annotations

import pytest

from pybi.semanticmodel import Column, Measure, Relationship, SemanticModel, Table
from pybi.serialization import deserialize, serialize


def _build_small_model() -> SemanticModel:
    """Build a small semantic model: 1 table, 5 columns, 2 measures."""
    columns = [
        Column(name="SalesDate", data_type="dateTime", summarize_by="none"),
        Column(
            name="Amount",
            data_type="decimal",
            format_string="$ #,##0.00",
            summarize_by="sum",
        ),
        Column(name="ProductKey", data_type="int64", is_key=True, summarize_by="none"),
        Column(name="CustomerKey", data_type="int64", summarize_by="none"),
        Column(name="Quantity", data_type="int64", summarize_by="sum"),
    ]
    measures = [
        Measure(
            name="Total Sales",
            expression="SUM(Sales[Amount])",
            format_string="$ #,##0.00",
            display_folder="Key Metrics",
        ),
        Measure(
            name="Total Quantity",
            expression="SUM(Sales[Quantity])",
            format_string="#,##0",
            display_folder="Key Metrics",
        ),
    ]
    table = Table(name="Sales", columns=columns, measures=measures)
    return SemanticModel(name="SalesModel", culture="en-US", tables=[table])


def _build_large_model() -> SemanticModel:
    """Build a large semantic model: 10 tables, 10 columns + 5 measures each."""
    tables = []
    for t in range(10):
        columns = [
            Column(
                name=f"Column{c}",
                data_type="string" if c % 3 != 0 else "int64",
                is_key=(c == 0),
                summarize_by="none" if c % 2 == 0 else "sum",
            )
            for c in range(10)
        ]
        measures = [
            Measure(
                name=f"Measure{m}",
                expression=f"SUM(Table{t}[Column{m}])",
                display_folder="Metrics",
            )
            for m in range(5)
        ]
        tables.append(Table(name=f"Table{t}", columns=columns, measures=measures))

    relationships = [
        Relationship(
            name=f"Table0_Table{t}",
            from_table="Table0",
            from_column="Column0",
            to_table=f"Table{t}",
            to_column="Column0",
        )
        for t in range(1, 10)
    ]
    return SemanticModel(
        name="LargeModel",
        culture="en-US",
        tables=tables,
        relationships=relationships,
    )


_SMALL_MODEL = _build_small_model()
_LARGE_MODEL = _build_large_model()
_SMALL_JSON = serialize(_SMALL_MODEL)
_LARGE_JSON = serialize(_LARGE_MODEL)


def test_serialize_small_model(benchmark: pytest.FixtureRequest) -> None:
    """Benchmark serializing a small semantic model to JSON."""
    benchmark(serialize, _SMALL_MODEL)


def test_serialize_large_model(benchmark: pytest.FixtureRequest) -> None:
    """Benchmark serializing a large semantic model to JSON."""
    benchmark(serialize, _LARGE_MODEL)


def test_deserialize_small_model(benchmark: pytest.FixtureRequest) -> None:
    """Benchmark deserializing a small semantic model from JSON."""
    benchmark(deserialize, SemanticModel, _SMALL_JSON)


def test_deserialize_large_model(benchmark: pytest.FixtureRequest) -> None:
    """Benchmark deserializing a large semantic model from JSON."""
    benchmark(deserialize, SemanticModel, _LARGE_JSON)
