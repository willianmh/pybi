import json
from pathlib import Path

import pytest

from pybi.expressions.filter import Filter, FilterTypeEnum

FILTERS_DIR = Path("../pbi-samples/local/filters")

_filter_files = sorted(FILTERS_DIR.glob("**/*.json"))


@pytest.mark.parametrize(
    "filter_path",
    _filter_files,
    ids=[str(p.relative_to(FILTERS_DIR)) for p in _filter_files],
)
def test_filter_load(filter_path: Path) -> None:
    raw: list[dict] = json.loads(filter_path.read_text())
    filters = [Filter.model_validate(item) for item in raw]

    assert len(filters) == len(raw)
    for f in filters:
        assert isinstance(f, Filter)
        assert isinstance(f.type, FilterTypeEnum)
        assert f.name is None or isinstance(f.name, str)


@pytest.mark.parametrize(
    "filter_path",
    _filter_files,
    ids=[str(p.relative_to(FILTERS_DIR)) for p in _filter_files],
)
def test_filter_roundtrip(filter_path: Path) -> None:
    raw: list[dict] = json.loads(filter_path.read_text())
    filters = [Filter.model_validate(item) for item in raw]
    serialized = [f.model_dump(mode="json", exclude_unset=True) for f in filters]

    assert serialized == raw
