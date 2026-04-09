from __future__ import annotations

from pybi.serialization.strategies import PbirStrategy
from pybi.serialization.transport import LocalTransport


def test_bench_report_pbir_deserialize_realistic(benchmark, report_parts) -> None:
    benchmark(PbirStrategy().deserialize, report_parts)


def test_bench_report_pbir_serialize_realistic(benchmark, report_realistic) -> None:
    benchmark(PbirStrategy().serialize, report_realistic)


def test_bench_report_pbir_roundtrip_mem_realistic(benchmark, report_parts) -> None:
    strategy = PbirStrategy()

    def run() -> None:
        report = strategy.deserialize(report_parts)
        strategy.serialize(report)

    benchmark(run)


def test_bench_report_pbir_roundtrip_io_realistic(
    benchmark, report_fixture_root, tmp_path
) -> None:
    strategy = PbirStrategy()
    transport = LocalTransport()
    output_root = tmp_path / "report_output"

    def run() -> None:
        input_parts = transport.read_parts(report_fixture_root)
        report = strategy.deserialize(input_parts)
        parts = strategy.serialize(report)
        transport.write_parts(parts, output_root, clean=True)

    benchmark(run)
