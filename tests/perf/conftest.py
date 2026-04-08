"""Shared fixtures and parametrization for TMDL parsing performance tests.

All TMDL files are read from disk exactly once at conftest import time and
stored in the module-level ``_ALL_TMDL_FILES`` dict.  Every fixture and
parametrized benchmark operates on that in-memory dict — there is no further
disk I/O during the benchmark runs.
"""

from pathlib import Path

import pytest

from pybi.semanticmodel.definition import SemanticModelDefinition
from pybi.serialization.parsers.tmdl.grammar import DEFINITION_PREFIX
from pybi.serialization.parsers.tmdl.loader import TMDLPartsLoader
from pybi.serialization.parsers.tmdl.parser import parse_tmdl
from pybi.serialization.transport.local import LocalTransport

# ---------------------------------------------------------------------------
# Sample location
# ---------------------------------------------------------------------------

_SAMPLES_ROOT = Path("../pbi-samples/pbi/pbir/11.25")
_AI_SAMPLE = _SAMPLES_ROOT / "ai" / "Artificial Intelligence Sample.SemanticModel"


def _read_tmdl_files(sample_path: Path) -> dict[str, str]:
    """Load definition/*.tmdl as {rel_path: text}.  Called once at import time."""
    parts = LocalTransport().read_parts(sample_path)
    return {
        p.path[len(DEFINITION_PREFIX) :]: p.as_text()
        for p in parts
        if p.path.startswith(DEFINITION_PREFIX) and p.path.endswith(".tmdl")
    }


# Single disk read — all benchmarks draw from this dict.
_ALL_TMDL_FILES: dict[str, str] = (
    _read_tmdl_files(_AI_SAMPLE) if _AI_SAMPLE.exists() else {}
)

# ---------------------------------------------------------------------------
# Dynamic parametrization for per-file benchmarks
# ---------------------------------------------------------------------------


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """Parametrize ``tmdl_file_item`` from the in-memory dict at collection time."""
    if "tmdl_file_item" in metafunc.fixturenames:
        items = sorted(_ALL_TMDL_FILES.items())
        ids = [path.replace("/", "__").replace(".", "_") for path, _ in items]
        metafunc.parametrize("tmdl_file_item", items, ids=ids)


# ---------------------------------------------------------------------------
# Session-scoped fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def tmdl_files() -> dict[str, str]:
    """All TMDL files for the AI sample, already in memory."""
    return _ALL_TMDL_FILES


@pytest.fixture(scope="session")
def table_files(tmdl_files: dict[str, str]) -> dict[str, str]:
    """Subset of tmdl_files containing only table definitions."""
    return {k: v for k, v in tmdl_files.items() if k.startswith("tables/")}


@pytest.fixture(scope="session")
def table_asts(table_files: dict[str, str]) -> dict[str, list]:
    """Pre-parsed ASTs for table files — isolates the transform stage."""
    return {path: parse_tmdl(text, path) for path, text in table_files.items()}


@pytest.fixture(scope="session")
def parsed_definition(tmdl_files: dict[str, str]) -> SemanticModelDefinition:
    """Fully parsed SemanticModelDefinition — input for write benchmarks."""
    return SemanticModelDefinition(**TMDLPartsLoader(tmdl_files).load())
