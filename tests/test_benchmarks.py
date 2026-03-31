"""Performance benchmarks for pybi."""

import pytest
from pydantic import BaseModel

from pybi.expressions import hello


# -- Pydantic model validation benchmarks ------------------------------------

class SimpleModel(BaseModel):
    name: str
    value: int
    active: bool


class NestedModel(BaseModel):
    title: str
    items: list[SimpleModel]
    metadata: dict[str, str]


SIMPLE_PAYLOAD = {"name": "test", "value": 42, "active": True}

NESTED_PAYLOAD = {
    "title": "benchmark",
    "items": [
        {"name": f"item_{i}", "value": i, "active": i % 2 == 0}
        for i in range(20)
    ],
    "metadata": {f"key_{i}": f"value_{i}" for i in range(10)},
}


def test_bench_simple_model_validation(benchmark):
    """Benchmark Pydantic validation of a flat model."""
    benchmark(SimpleModel.model_validate, SIMPLE_PAYLOAD)


def test_bench_nested_model_validation(benchmark):
    """Benchmark Pydantic validation of a nested model with lists and dicts."""
    benchmark(NestedModel.model_validate, NESTED_PAYLOAD)


def test_bench_model_serialization_json(benchmark):
    """Benchmark Pydantic JSON serialization round-trip."""
    instance = NestedModel.model_validate(NESTED_PAYLOAD)
    benchmark(instance.model_dump_json)


def test_bench_model_serialization_dict(benchmark):
    """Benchmark Pydantic dict serialization."""
    instance = NestedModel.model_validate(NESTED_PAYLOAD)
    benchmark(instance.model_dump)


# -- Core module benchmarks ---------------------------------------------------

def test_bench_hello(benchmark):
    """Benchmark the hello function from expressions module."""
    benchmark(hello)
