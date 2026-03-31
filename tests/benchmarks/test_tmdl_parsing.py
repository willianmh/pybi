"""Performance benchmarks for TMDL parsing."""

from __future__ import annotations

import pytest

from pybi.semanticmodel.tmdl import parse_tmdl

_SMALL_TMDL = """\
model SalesModel
    culture: en-US

table Sales
    /// Total sales amount
    measure 'Total Sales' = SUM(Sales[Amount])
        formatString: $ #,##0.00
        displayFolder: Key Metrics
    measure 'Total Quantity' = SUM(Sales[Quantity])
        formatString: #,##0
        displayFolder: Key Metrics
    column SalesDate
        dataType: dateTime
        summarizeBy: none
    column Amount
        dataType: decimal
        formatString: $ #,##0.00
        summarizeBy: sum
    column ProductKey
        dataType: int64
        isKey
        summarizeBy: none
    column CustomerKey
        dataType: int64
        summarizeBy: none
    column Quantity
        dataType: int64
        summarizeBy: sum
"""


def _build_large_tmdl() -> str:
    """Generate a large TMDL document: 10 tables, 10 columns, 5 measures each."""
    lines = ["model LargeModel", "    culture: en-US", ""]
    for t in range(10):
        lines.append(f"table Table{t}")
        for m in range(5):
            lines.append(f"    measure 'Measure{m}' = SUM(Table{t}[Column{m}])")
            lines.append("        displayFolder: Metrics")
        for c in range(10):
            data_type = "string" if c % 3 != 0 else "int64"
            lines.append(f"    column Column{c}")
            lines.append(f"        dataType: {data_type}")
            if c == 0:
                lines.append("        isKey")
            lines.append("        summarizeBy: none")
        lines.append("")
    return "\n".join(lines)


_LARGE_TMDL = _build_large_tmdl()


def test_parse_small_tmdl(benchmark: pytest.FixtureRequest) -> None:
    """Benchmark parsing a small TMDL document."""
    benchmark(parse_tmdl, _SMALL_TMDL)


def test_parse_large_tmdl(benchmark: pytest.FixtureRequest) -> None:
    """Benchmark parsing a large TMDL document."""
    benchmark(parse_tmdl, _LARGE_TMDL)
