from __future__ import annotations

from pathlib import Path

import pytest

from pybi.report.report import Report
from pybi.semanticmodel import (
    Column,
    Measure,
    Model,
    SemanticModel,
    SemanticModelDefinition,
    Table,
)
from pybi.serialization.transport import LocalTransport
from pybi.fabric.fabric import default_definition_pbism, default_semanticmodel_platform

_FIXTURES_ROOT = Path(__file__).parent / "fixtures" / "ai"
_SEMANTIC_MODEL_ROOT = _FIXTURES_ROOT / "Artificial Intelligence Sample.SemanticModel"
_REPORT_ROOT = _FIXTURES_ROOT / "Artificial Intelligence Sample.Report"


@pytest.fixture(scope="session")
def semantic_model_fixture_root() -> Path:
    return _SEMANTIC_MODEL_ROOT


@pytest.fixture(scope="session")
def report_fixture_root() -> Path:
    return _REPORT_ROOT


@pytest.fixture(scope="session")
def semantic_model_parts(semantic_model_fixture_root: Path):
    return LocalTransport().read_parts(semantic_model_fixture_root)


@pytest.fixture(scope="session")
def report_parts(report_fixture_root: Path):
    return LocalTransport().read_parts(report_fixture_root)


@pytest.fixture(scope="session")
def semantic_model_realistic(semantic_model_fixture_root: Path) -> SemanticModel:
    return SemanticModel.read(semantic_model_fixture_root)


@pytest.fixture(scope="session")
def report_realistic(report_fixture_root: Path) -> Report:
    return Report.read(report_fixture_root)


@pytest.fixture(scope="session")
def semantic_model_worst_case() -> SemanticModel:
    """Synthetic heavy model used as a deterministic worst-case JSON workload."""
    tables: list[Table] = []

    for table_idx in range(60):
        columns = [
            Column(
                name=f"Column_{table_idx}_{column_idx}",
                dataType="string" if column_idx % 4 else "int64",
                summarizeBy="none",
            )
            for column_idx in range(35)
        ]
        measures = [
            Measure(
                name=f"Measure_{table_idx}_{measure_idx}",
                expression=(
                    " + ".join(
                        [
                            f"SUM(Table_{table_idx}[Column_{table_idx}_{column_idx}])"
                            for column_idx in range(8)
                        ]
                    )
                ),
                displayFolder="Stress",
            )
            for measure_idx in range(12)
        ]
        tables.append(Table(name=f"Table_{table_idx}", columns=columns, measures=measures))

    definition = SemanticModelDefinition(model=Model(culture="en-US", tables=tables))
    return SemanticModel(
        definition=definition,
        item_definition=default_definition_pbism(),
        platform=default_semanticmodel_platform(),
    )
