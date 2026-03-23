import json
from pathlib import Path

import pytest

from pybi.expressions.filter import Filter
from pybi.report.legacy.legacy_model import (
    ReportConfig,
    ReportJsonDefinition,
    SectionConfig,
    VisualContainerConfig,
)

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
    r = ReportJsonDefinition.model_validate(raw)

    assert isinstance(r, ReportJsonDefinition)


@pytest.mark.parametrize(
    "report_path",
    _report_files,
    ids=[str(p.relative_to(REPORT_DIR)) for p in _report_files],
)
def test_filter_roundtrip(report_path: Path) -> None:
    raw: dict = json.loads(report_path.read_text())
    r = ReportJsonDefinition.model_validate(raw)
    serialized = r.model_dump(mode="json", exclude_unset=True, exclude_none=True)

    assert serialized == raw


def _check(model_cls: type, raw_data: dict, label: str, errors: list[str]) -> None:
    """Validate load + roundtrip for one component, appending any failures to errors."""
    try:
        obj = model_cls.model_validate(raw_data)
    except Exception as e:
        errors.append(f"{label} [load]: {e}")
        return

    dumped = obj.model_dump(mode="json", exclude_unset=True, exclude_none=True)
    if dumped != raw_data:
        missing = sorted(set(raw_data) - set(dumped))
        extra = sorted(set(dumped) - set(raw_data))
        changed = sorted(
            k for k in raw_data if k in dumped and raw_data[k] != dumped[k]
        )
        parts: list[str] = []
        if missing:
            parts.append(f"missing keys: {missing}")
        if extra:
            parts.append(f"extra keys: {extra}")
        if changed:
            parts.append(f"changed keys: {changed}")
        errors.append(f"{label} [roundtrip]: {', '.join(parts) or 'values differ'}")


@pytest.mark.parametrize(
    "report_path",
    _report_files,
    ids=[str(p.relative_to(REPORT_DIR)) for p in _report_files],
)
def test_report_components(report_path: Path) -> None:
    """Validates load and roundtrip for each embedded JSON layer independently,
    so failures identify the exact Pydantic class and structural location, e.g.:
        sections[1].visualContainers[4].VisualContainerConfig [roundtrip]: changed keys: ['x']
    """
    raw: dict = json.loads(report_path.read_text())
    errors: list[str] = []

    _check(ReportConfig, json.loads(raw.get("config", "{}")), "ReportConfig", errors)

    for i, f in enumerate(json.loads(raw.get("filters", "[]"))):
        _check(Filter, f, f"filters[{i}]", errors)

    for si, section in enumerate(raw.get("sections", [])):
        label = f"sections[{si}]"

        _check(
            SectionConfig,
            json.loads(section.get("config", "{}")),
            f"{label}.SectionConfig",
            errors,
        )

        for fi, f in enumerate(json.loads(section.get("filters", "[]"))):
            _check(Filter, f, f"{label}.filters[{fi}]", errors)

        for vi, vc in enumerate(section.get("visualContainers", [])):
            vc_label = f"{label}.visualContainers[{vi}]"

            _check(
                VisualContainerConfig,
                json.loads(vc.get("config", "{}")),
                f"{vc_label}.VisualContainerConfig",
                errors,
            )

            for fi, f in enumerate(json.loads(vc.get("filters", "[]"))):
                _check(Filter, f, f"{vc_label}.filters[{fi}]", errors)

    if errors:
        pytest.fail("\n\n".join(errors))
