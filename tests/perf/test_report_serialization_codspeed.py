from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("pytest_benchmark")

from pybi.report.report import Report
from pybi.serialization.strategies import PbirStrategy, ReportJsonStrategy
from pybi.serialization.transport import LocalTransport
from pybi.serialization.types import Part

pytestmark = [pytest.mark.perf, pytest.mark.benchmark]

REPO_ROOT = Path(__file__).parents[2]
LEGACY_ROOT = REPO_ROOT / "samples" / "legacy" / "11.25"
PBIR_ROOT = REPO_ROOT / "samples" / "pbir" / "11.25"


@pytest.fixture(scope="module")
def local_transport() -> LocalTransport:
    return LocalTransport()


@pytest.fixture(scope="module")
def legacy_report_roots() -> list[Path]:
    return sorted(LEGACY_ROOT.glob("*/*.Report"))


@pytest.fixture(scope="module")
def pbir_report_roots() -> list[Path]:
    return sorted(PBIR_ROOT.glob("*/*.Report"))


@pytest.fixture(scope="module")
def legacy_parts_by_report(
    local_transport: LocalTransport,
    legacy_report_roots: list[Path],
) -> dict[str, list[Part]]:
    return {
        report_root.name: local_transport.read_parts(report_root)
        for report_root in legacy_report_roots
    }


@pytest.fixture(scope="module")
def pbir_parts_by_report(
    local_transport: LocalTransport,
    pbir_report_roots: list[Path],
) -> dict[str, list[Part]]:
    return {
        report_root.name: local_transport.read_parts(report_root)
        for report_root in pbir_report_roots
    }


def _clone_pbir_parts_with_page_scale(parts: list[Part], clone_factor: int) -> list[Part]:
    scaled: list[Part] = list(parts)

    page_parts = [p for p in parts if p.path.startswith("definition/pages/")]
    for clone_idx in range(1, clone_factor + 1):
        suffix = f"__clone_{clone_idx:02d}"
        for part in page_parts:
            page_name = part.path.split("/")[2]
            scaled.append(
                Part(
                    path=part.path.replace(
                        f"definition/pages/{page_name}",
                        f"definition/pages/{page_name}{suffix}",
                        1,
                    ),
                    payload=part.payload,
                )
            )

    return scaled


@pytest.fixture(scope="module")
def largest_pbir_parts(pbir_parts_by_report: dict[str, list[Part]]) -> list[Part]:
    return max(
        pbir_parts_by_report.values(),
        key=lambda parts: sum(1 for p in parts if p.path.endswith("/visual.json")),
    )


@pytest.fixture(scope="module")
def scaled_pbir_parts(largest_pbir_parts: list[Part]) -> list[Part]:
    # deterministic in-memory scaling for page/visual-heavy benchmarks
    return _clone_pbir_parts_with_page_scale(largest_pbir_parts, clone_factor=2)


@pytest.fixture(scope="module")
def legacy_report_parts(legacy_parts_by_report: dict[str, list[Part]]) -> list[Part]:
    return max(
        legacy_parts_by_report.values(),
        key=lambda parts: sum(1 for p in parts if p.path.endswith("visualContainer.json")),
    )


@pytest.mark.perf
@pytest.mark.benchmark(group="report-strategy")
def test_benchmark_pbir_deserialize(
    benchmark,
    largest_pbir_parts: list[Part],
) -> None:
    strategy = PbirStrategy()
    benchmark(strategy.deserialize, largest_pbir_parts)


@pytest.mark.perf
@pytest.mark.benchmark(group="report-strategy")
def test_benchmark_pbir_serialize(
    benchmark,
    largest_pbir_parts: list[Part],
) -> None:
    strategy = PbirStrategy()
    report = strategy.deserialize(largest_pbir_parts)
    benchmark(strategy.serialize, report)


@pytest.mark.perf
@pytest.mark.benchmark(group="report-strategy")
def test_benchmark_report_json_deserialize(
    benchmark,
    legacy_report_parts: list[Part],
) -> None:
    strategy = ReportJsonStrategy()
    benchmark(strategy.deserialize, legacy_report_parts)


@pytest.mark.perf
@pytest.mark.benchmark(group="report-strategy")
def test_benchmark_report_json_serialize(
    benchmark,
    legacy_report_parts: list[Part],
) -> None:
    strategy = ReportJsonStrategy()
    report = strategy.deserialize(legacy_report_parts)
    benchmark(strategy.serialize, report)


@pytest.mark.perf
@pytest.mark.benchmark(group="report-strategy-scale")
def test_benchmark_pbir_deserialize_scaled_pages(
    benchmark,
    scaled_pbir_parts: list[Part],
) -> None:
    strategy = PbirStrategy()
    benchmark(strategy.deserialize, scaled_pbir_parts)


@pytest.mark.perf
@pytest.mark.benchmark(group="report-strategy-scale")
def test_benchmark_pbir_serialize_scaled_pages(
    benchmark,
    scaled_pbir_parts: list[Part],
) -> None:
    strategy = PbirStrategy()
    scaled_report = strategy.deserialize(scaled_pbir_parts)
    benchmark(strategy.serialize, scaled_report)


@pytest.mark.perf
@pytest.mark.benchmark(group="report-read")
@pytest.mark.parametrize(
    "root_path",
    [
        PBIR_ROOT / "ai" / "Artificial Intelligence Sample.Report",
        LEGACY_ROOT / "ai" / "Artificial Intelligence Sample.Report",
    ],
    ids=["pbir", "legacy"],
)
def test_benchmark_report_read(benchmark, root_path: Path) -> None:
    benchmark(Report.read, root_path)
