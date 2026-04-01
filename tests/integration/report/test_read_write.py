"""Integration tests for Report.read() and Report.write().

These tests exercise the public Report API — auto-format detection,
private-state wiring (_ROOT_PATH / _source_format), and write()
path/format fallback logic. Structural assertions (page counts,
visual names, etc.) are covered by test_pbir_strategy.py.
"""

import tempfile
from pathlib import Path

import pytest

from pybi.report.pbir.definition import PbirReportDefinition
from pybi.report.report import Report
from pybi.report.types import ReportFormat

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_PBIR_ROOT = Path("../pbi-samples/pbi/pbir/11.25")

pytestmark = pytest.mark.skipif(
    not Path("../pbi-samples").exists(),
    reason="pbi-samples repository not available; clone https://github.com/willianmh/pbi-samples",
)
_AI_REPORT = _PBIR_ROOT / "ai" / "Artificial Intelligence Sample.Report"

# Curated list of PBIR-format samples (mirrors test_pbir_strategy.py).
# covid-bakeoff is excluded: it lives under samples/pbir/ but is legacy format.
_PBIR_SAMPLE_DIRS: dict[str, Path] = {
    "ai": _PBIR_ROOT / "ai" / "Artificial Intelligence Sample.Report",
    "human-resources": _PBIR_ROOT
    / "human-resources"
    / "Human Resources Sample PBIX.Report",
    "covid-19-us": _PBIR_ROOT / "covid-19-us" / "COVID-19 US Tracking Sample.Report",
    "life-expectancy": _PBIR_ROOT
    / "life-expectancy"
    / "Life expectancy v202009.Report",
    "revenue-opportunities": _PBIR_ROOT
    / "revenue-opportunities"
    / "Revenue Opportunities.Report",
    "sales-return": _PBIR_ROOT
    / "sales-return"
    / "Sales & Returns Sample v201912.Report",
    "supply-chain": _PBIR_ROOT / "supply-chain" / "Supply Chain Sample.Report",
}


# ---------------------------------------------------------------------------
# TestRead — Report.read() integration
# ---------------------------------------------------------------------------


class TestRead:
    """Report.read() auto-detects format and wires private state correctly."""

    @pytest.fixture(scope="class")
    def ai_report(self):
        return Report.read(str(_AI_REPORT))

    def test_smoke_all_samples(self):
        for root in _PBIR_SAMPLE_DIRS.values():
            report = Report.read(str(root))
            assert isinstance(report.definition, PbirReportDefinition)

    def test_detects_pbir_format(self, ai_report):
        assert ai_report._source_format is ReportFormat.PBIR

    def test_sets_root_path(self, ai_report):
        assert ai_report._ROOT_PATH == str(_AI_REPORT)

    def test_definition_is_pbir(self, ai_report):
        assert isinstance(ai_report.definition, PbirReportDefinition)

    def test_platform_present(self, ai_report):
        assert ai_report.platform is not None

    def test_item_definition_present(self, ai_report):
        assert ai_report.item_definition is not None


# ---------------------------------------------------------------------------
# TestWrite — Report.write() path/format fallback and error cases
# ---------------------------------------------------------------------------


class TestWrite:
    """Report.write() uses fallback root_path and rejects cross-format writes."""

    def test_write_explicit_path(self):
        report = Report.read(str(_AI_REPORT))
        with tempfile.TemporaryDirectory() as tmp:
            report.write(root_path=tmp, format=None)
            reloaded = Report.read(tmp)
            assert isinstance(reloaded.definition, PbirReportDefinition)

    def test_write_uses_root_path_fallback(self):
        report = Report.read(str(_AI_REPORT))
        with tempfile.TemporaryDirectory() as tmp:
            report._ROOT_PATH = tmp
            report.write(root_path=None, format=None)
            reloaded = Report.read(tmp)
        assert isinstance(reloaded.definition, PbirReportDefinition)

    def test_write_raises_without_root_path(self):
        report = Report.read(str(_AI_REPORT))
        report._ROOT_PATH = None
        with pytest.raises(ValueError, match="root_path"):
            report.write(root_path=None, format=None)

    def test_write_raises_on_format_mismatch(self):
        report = Report.read(str(_AI_REPORT))
        with tempfile.TemporaryDirectory() as tmp:
            with pytest.raises(ValueError):
                report.write(root_path=tmp, format=ReportFormat.LEGACY)


# ---------------------------------------------------------------------------
# TestRoundtrip — end-to-end via Report public API
# ---------------------------------------------------------------------------


class TestRoundtrip:
    """read() → write() → read() through the Report public API."""

    @pytest.fixture(
        params=sorted(_PBIR_SAMPLE_DIRS.keys()),
        ids=lambda k: k,
    )
    def roundtripped(self, request):
        root = _PBIR_SAMPLE_DIRS[request.param]
        original = Report.read(str(root))
        with tempfile.TemporaryDirectory() as tmp:
            original.write(root_path=tmp, format=None)
            reloaded = Report.read(tmp)
        return original, reloaded

    def test_source_format_preserved(self, roundtripped):
        original, reloaded = roundtripped
        assert reloaded._source_format is original._source_format

    def test_page_count_preserved(self, roundtripped):
        original, reloaded = roundtripped
        assert len(reloaded.definition.pages) == len(original.definition.pages)

    def test_visual_count_preserved(self, roundtripped):
        original, reloaded = roundtripped
        orig = sum(len(p.visuals) for p in original.definition.pages)
        new = sum(len(p.visuals) for p in reloaded.definition.pages)
        assert new == orig

    def test_bookmark_count_preserved(self, roundtripped):
        original, reloaded = roundtripped
        assert len(reloaded.definition.bookmarks) == len(original.definition.bookmarks)

    def test_platform_display_name_preserved(self, roundtripped):
        original, reloaded = roundtripped
        assert (
            reloaded.platform.metadata.displayName
            == original.platform.metadata.displayName
        )
