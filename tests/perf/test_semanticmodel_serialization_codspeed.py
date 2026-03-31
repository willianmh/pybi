from pathlib import Path

import pytest

from pybi.semanticmodel.semanticmodel import SemanticModel
from pybi.semanticmodel.types import SemanticModelFormat
from pybi.serialization.strategies import ModelBimStrategy, TmdlStrategy
from pybi.serialization.transport.local import LocalTransport

SAMPLE_ROOT = Path(
    "samples/legacy/11.25/supply-chain"
    "/Supply Chain Sample.SemanticModel"
)


@pytest.fixture(scope="session")
def local_transport() -> LocalTransport:
    return LocalTransport()


@pytest.fixture(scope="session")
def legacy_parts(local_transport: LocalTransport):
    return local_transport.read_parts(SAMPLE_ROOT)


@pytest.fixture(scope="session")
def model_bim_strategy() -> ModelBimStrategy:
    return ModelBimStrategy()


@pytest.fixture(scope="session")
def tmdl_strategy() -> TmdlStrategy:
    return TmdlStrategy()


@pytest.fixture(scope="session")
def legacy_model(legacy_parts, model_bim_strategy: ModelBimStrategy) -> SemanticModel:
    return model_bim_strategy.deserialize(legacy_parts)


@pytest.fixture(scope="session")
def tmdl_parts(legacy_model: SemanticModel, tmdl_strategy: TmdlStrategy):
    # Derived from deterministic legacy sample input.
    return tmdl_strategy.serialize(legacy_model)


@pytest.fixture(scope="session")
def tmdl_root_path(
    tmp_path_factory: pytest.TempPathFactory,
    local_transport: LocalTransport,
    tmdl_parts,
) -> Path:
    root = tmp_path_factory.mktemp("semanticmodel_tmdl_sample")
    local_transport.write_parts(parts=tmdl_parts, root=root)
    return root


# ---------------------------------------------------------------------------
# Strategy-only benchmarks (in-memory Part list)
# ---------------------------------------------------------------------------


def test_bench_tmdl_deserialize(benchmark, tmdl_strategy: TmdlStrategy, tmdl_parts):
    benchmark(tmdl_strategy.deserialize, tmdl_parts)


def test_bench_tmdl_serialize(benchmark, tmdl_strategy: TmdlStrategy, legacy_model: SemanticModel):
    benchmark(tmdl_strategy.serialize, legacy_model)


def test_bench_model_bim_deserialize(
    benchmark,
    model_bim_strategy: ModelBimStrategy,
    legacy_parts,
):
    benchmark(model_bim_strategy.deserialize, legacy_parts)


def test_bench_model_bim_serialize(
    benchmark,
    model_bim_strategy: ModelBimStrategy,
    legacy_model: SemanticModel,
):
    benchmark(model_bim_strategy.serialize, legacy_model)


# ---------------------------------------------------------------------------
# End-to-end benchmarks (LocalTransport + strategy overhead)
# ---------------------------------------------------------------------------


def test_bench_semanticmodel_read_legacy(benchmark):
    benchmark(SemanticModel.read, SAMPLE_ROOT)


def test_bench_semanticmodel_read_tmdl(benchmark, tmdl_root_path: Path):
    benchmark(SemanticModel.read, tmdl_root_path)


def test_bench_semanticmodel_write_legacy(
    benchmark,
    legacy_model: SemanticModel,
    tmp_path: Path,
):
    out_root = tmp_path / "legacy_out"

    def run():
        legacy_model.write(out_root, format=SemanticModelFormat.LEGACY)

    benchmark(run)


def test_bench_semanticmodel_write_tmdl(
    benchmark,
    legacy_model: SemanticModel,
    tmp_path: Path,
):
    out_root = tmp_path / "tmdl_out"

    def run():
        legacy_model.write(out_root, format=SemanticModelFormat.TMDL)

    benchmark(run)
