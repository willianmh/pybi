"""Performance benchmarks for pybi using pytest-codspeed."""

from pathlib import Path

import pytest

from pybi import SemanticModel
from pybi.serialization.parsers.tmdl.lexer import TMDLLexer
from pybi.serialization.parsers.tmdl.loader import TMDLPartsLoader
from pybi.serialization.parsers.tmdl.writer import TMDLPartsWriter
from pybi.serialization.transport.local import LocalTransport

# ---------------------------------------------------------------------------
# Sample paths
# ---------------------------------------------------------------------------

_SAMPLES_ROOT = Path("samples/pbir/11.25")

_AI_SEMANTIC_MODEL = _SAMPLES_ROOT / "ai" / "Artificial Intelligence Sample.SemanticModel"
_HR_SEMANTIC_MODEL = (
    _SAMPLES_ROOT / "human-resources" / "Human Resources Sample PBIX.SemanticModel"
)

_CASES_TMDL = _AI_SEMANTIC_MODEL / "definition" / "tables" / "Cases.tmdl"
_EMPLOYEE_TMDL = _HR_SEMANTIC_MODEL / "definition" / "tables" / "Employee.tmdl"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def all_tmdl_files() -> list[Path]:
    return sorted(_SAMPLES_ROOT.glob("**/*.tmdl"))


@pytest.fixture(scope="session")
def ai_tmdl_parts() -> dict[str, str]:
    transport = LocalTransport()
    parts = transport.read_parts(str(_AI_SEMANTIC_MODEL))
    return {
        p.path.removeprefix("definition/"): p.as_text()
        for p in parts
        if p.path.startswith("definition/") and p.path.endswith(".tmdl")
    }


@pytest.fixture(scope="session")
def hr_tmdl_parts() -> dict[str, str]:
    transport = LocalTransport()
    parts = transport.read_parts(str(_HR_SEMANTIC_MODEL))
    return {
        p.path.removeprefix("definition/"): p.as_text()
        for p in parts
        if p.path.startswith("definition/") and p.path.endswith(".tmdl")
    }


@pytest.fixture(scope="session")
def ai_semantic_model() -> SemanticModel:
    return SemanticModel.read(str(_AI_SEMANTIC_MODEL))


# ---------------------------------------------------------------------------
# TMDL Lexer benchmarks
# ---------------------------------------------------------------------------


def test_lexer_large_table_file(benchmark) -> None:
    """Benchmark tokenizing a large table TMDL file (Cases.tmdl, ~334 lines)."""
    text = _CASES_TMDL.read_text(encoding="utf-8")

    def run():
        return list(TMDLLexer(text, file_path=str(_CASES_TMDL)).tokenize())

    benchmark(run)


def test_lexer_all_sample_files(benchmark, all_tmdl_files: list[Path]) -> None:
    """Benchmark tokenizing all TMDL sample files."""
    contents = [(p, p.read_text(encoding="utf-8")) for p in all_tmdl_files]

    def run():
        for path, text in contents:
            list(TMDLLexer(text, file_path=str(path)).tokenize())

    benchmark(run)


# ---------------------------------------------------------------------------
# TMDL loader (deserialization) benchmarks
# ---------------------------------------------------------------------------


def test_tmdl_loader_ai_semantic_model(benchmark, ai_tmdl_parts: dict[str, str]) -> None:
    """Benchmark loading (parsing + transforming) the AI sample semantic model."""

    def run():
        return TMDLPartsLoader(ai_tmdl_parts).load()

    benchmark(run)


def test_tmdl_loader_hr_semantic_model(benchmark, hr_tmdl_parts: dict[str, str]) -> None:
    """Benchmark loading the Human Resources sample semantic model."""

    def run():
        return TMDLPartsLoader(hr_tmdl_parts).load()

    benchmark(run)


# ---------------------------------------------------------------------------
# TMDL writer (serialization) benchmarks
# ---------------------------------------------------------------------------


def test_tmdl_writer_ai_semantic_model(benchmark, ai_semantic_model: SemanticModel) -> None:
    """Benchmark serializing the AI sample semantic model back to TMDL parts."""

    def run():
        return TMDLPartsWriter().write(ai_semantic_model.definition)

    benchmark(run)


# ---------------------------------------------------------------------------
# End-to-end SemanticModel.read benchmark
# ---------------------------------------------------------------------------


def test_semantic_model_read_ai(benchmark) -> None:
    """Benchmark the full SemanticModel.read() pipeline for the AI sample."""

    def run():
        return SemanticModel.read(str(_AI_SEMANTIC_MODEL))

    benchmark(run)
