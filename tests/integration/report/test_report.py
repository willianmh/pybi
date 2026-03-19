import json
from pathlib import Path

import pytest

from pybi.report.legacy_model import ReportDefinition

REPO_ROOT = Path(__file__).parents[3]
REPORT_DIR = REPO_ROOT / "samples" / "local" / "reports"

_report_files = sorted(REPORT_DIR.glob("**/*.json"))


@pytest.mark.parametrize(
    "report_path",
    _report_files,
    ids=[str(p.relative_to(REPORT_DIR)) for p in _report_files],
)
def test_report_load(report_path: Path) -> None:
    raw: dict = json.loads(report_path.read_text())
    r = ReportDefinition.model_validate(raw)

    assert isinstance(r, ReportDefinition)


@pytest.mark.parametrize(
    "report_path",
    _report_files,
    ids=[str(p.relative_to(REPORT_DIR)) for p in _report_files],
)
def test_filter_roundtrip(report_path: Path) -> None:
    raw: dict = json.loads(report_path.read_text())
    r = ReportDefinition.model_validate(raw)
    serialized = r.model_dump(mode="json", exclude_unset=True, exclude_none=True)

    assert serialized == raw
