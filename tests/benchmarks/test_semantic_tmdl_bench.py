from __future__ import annotations

import pytest

from pybi.serialization.strategies import TmdlStrategy
from pybi.serialization.transport import LocalTransport


def test_bench_semantic_tmdl_deserialize_realistic(benchmark, semantic_model_parts) -> None:
    benchmark(TmdlStrategy().deserialize, semantic_model_parts)


def test_bench_semantic_tmdl_serialize_realistic(benchmark, semantic_model_realistic) -> None:
    benchmark(TmdlStrategy().serialize, semantic_model_realistic)


def test_bench_semantic_tmdl_roundtrip_mem_realistic(benchmark, semantic_model_parts) -> None:
    strategy = TmdlStrategy()

    def run() -> None:
        model = strategy.deserialize(semantic_model_parts)
        strategy.serialize(model)

    benchmark(run)


@pytest.mark.io_benchmark
def test_bench_semantic_tmdl_roundtrip_io_realistic(
    benchmark, semantic_model_fixture_root, tmp_path
) -> None:
    strategy = TmdlStrategy()
    transport = LocalTransport()
    output_root = tmp_path / "semantic_model_output"

    def run() -> None:
        input_parts = transport.read_parts(semantic_model_fixture_root)
        model = strategy.deserialize(input_parts)
        parts = strategy.serialize(model)
        transport.write_parts(parts, output_root, clean=True)

    benchmark(run)
