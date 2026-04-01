"""Integration tests for PbirStrategy against real sample directories.

Validates the full path: disk -> Parts -> PbirStrategy -> Report,
and the roundtrip: Report -> Parts -> Report.
"""

import json
import tempfile
from pathlib import Path

import pytest

from pybi.serialization.strategies.pbir import PbirStrategy
from pybi.serialization.transport.local import LocalTransport
from pybi.report.report import Report
from pybi.report.pbir.definition import PbirReportDefinition

# ---------------------------------------------------------------------------
# Sample directory paths (each points to the .Report folder)
# ---------------------------------------------------------------------------

_SAMPLES_ROOT = Path("../pbi-samples/pbi/pbir/11.25")

_SAMPLE_DIRS: dict[str, Path] = {
    "ai": _SAMPLES_ROOT / "ai" / "Artificial Intelligence Sample.Report",
    "human-resources": _SAMPLES_ROOT
    / "human-resources"
    / "Human Resources Sample PBIX.Report",
    "covid-19-us": _SAMPLES_ROOT / "covid-19-us" / "COVID-19 US Tracking Sample.Report",
    "life-expectancy": _SAMPLES_ROOT
    / "life-expectancy"
    / "Life expectancy v202009.Report",
    "revenue-opportunities": _SAMPLES_ROOT
    / "revenue-opportunities"
    / "Revenue Opportunities.Report",
    "sales-return": _SAMPLES_ROOT
    / "sales-return"
    / "Sales & Returns Sample v201912.Report",
    "supply-chain": _SAMPLES_ROOT / "supply-chain" / "Supply Chain Sample.Report",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_report(sample_name: str) -> Report:
    transport = LocalTransport()
    strategy = PbirStrategy()
    parts = transport.read_parts(str(_SAMPLE_DIRS[sample_name]))
    return strategy.deserialize(parts)


def _roundtrip(sample_name: str) -> tuple[Report, Report]:
    """Read a sample, serialize, write, re-read, deserialize."""
    transport = LocalTransport()
    strategy = PbirStrategy()

    parts = transport.read_parts(str(_SAMPLE_DIRS[sample_name]))
    original = strategy.deserialize(parts)

    roundtrip_parts = strategy.serialize(original)

    with tempfile.TemporaryDirectory() as tmpdir:
        transport.write_parts(roundtrip_parts, tmpdir)
        reread_parts = transport.read_parts(tmpdir)

    reread = strategy.deserialize(reread_parts)
    return original, reread


# ---------------------------------------------------------------------------
# TestReadOnAllSamples — parametrized smoke tests
# ---------------------------------------------------------------------------


class TestReadOnAllSamples:
    @pytest.fixture(
        params=sorted(_SAMPLE_DIRS.keys()),
        ids=lambda k: k,
    )
    def sample_name(self, request) -> str:
        return request.param

    @pytest.fixture
    def report(self, sample_name) -> Report:
        return _load_report(sample_name)

    @pytest.fixture
    def defn(self, report) -> PbirReportDefinition:
        assert isinstance(report.definition, PbirReportDefinition)
        return report.definition

    def test_read_does_not_crash(self, report):
        assert report is not None

    def test_definition_is_pbir(self, report):
        assert isinstance(report.definition, PbirReportDefinition)

    def test_has_version(self, defn):
        assert defn.version is not None
        assert defn.version.version is not None

    def test_has_report_metadata(self, defn):
        assert defn.report is not None

    def test_has_pages_metadata(self, defn):
        assert defn.pages_metadata is not None

    def test_has_pages(self, defn):
        assert len(defn.pages) >= 1

    def test_all_pages_have_visuals(self, defn):
        for page in defn.pages:
            assert len(page.visuals) >= 1, (
                f"Page {getattr(page.page, 'name', '?')} has no visuals"
            )

    def test_all_pages_have_names(self, defn):
        for page in defn.pages:
            name = getattr(page.page, "name", None)
            assert name, "Page with empty name found"

    def test_all_visuals_have_names(self, defn):
        for page in defn.pages:
            for vis in page.visuals:
                name = getattr(vis, "name", None)
                assert name, (
                    f"Visual without name in page {getattr(page.page, 'name', '?')}"
                )

    def test_platform_is_report(self, report):
        assert report.platform.metadata.type == "Report"

    def test_item_definition_present(self, report):
        assert report.item_definition is not None


# ---------------------------------------------------------------------------
# TestReadAISample — targeted assertions on a known sample
# ---------------------------------------------------------------------------


class TestReadAISample:
    @pytest.fixture(scope="class")
    def report(self) -> Report:
        return _load_report("ai")

    @pytest.fixture(scope="class")
    def defn(self, report) -> PbirReportDefinition:
        return report.definition

    def test_page_count(self, defn):
        assert len(defn.pages) == 3

    def test_total_visuals(self, defn):
        total = sum(len(p.visuals) for p in defn.pages)
        assert total == 235

    def test_mobile_states_present(self, defn):
        total = sum(len(p.mobile_states) for p in defn.pages)
        assert total == 37

    def test_bookmark_count(self, defn):
        assert len(defn.bookmarks) == 17

    def test_bookmarks_metadata(self, defn):
        assert defn.bookmarks_metadata is not None

    def test_bookmark_names_non_empty(self, defn):
        for bm in defn.bookmarks:
            assert bm.name, "Bookmark with empty name"

    def test_page_names(self, defn):
        names = {getattr(p.page, "name") for p in defn.pages}
        assert "ReportSection76c409e0c333d60bb1e2" in names
        assert "ReportSectionacd41c847407a998c130" in names
        assert "ReportSection909ea50e7939156807d6" in names

    def test_pages_metadata_page_order(self, defn):
        page_order = getattr(defn.pages_metadata, "pageOrder", None)
        assert page_order is not None
        assert len(page_order) == 3

    def test_display_name(self, report):
        assert report.platform.metadata.displayName == "Artificial Intelligence Sample"

    def test_version(self, defn):
        assert defn.version.version == "2.0.0"


# ---------------------------------------------------------------------------
# TestReadSupplyChainSample
# ---------------------------------------------------------------------------


class TestReadSupplyChainSample:
    @pytest.fixture(scope="class")
    def report(self) -> Report:
        return _load_report("supply-chain")

    @pytest.fixture(scope="class")
    def defn(self, report) -> PbirReportDefinition:
        return report.definition

    def test_page_count(self, defn):
        assert len(defn.pages) == 4

    def test_total_visuals(self, defn):
        total = sum(len(p.visuals) for p in defn.pages)
        assert total == 23

    def test_bookmark_count(self, defn):
        assert len(defn.bookmarks) == 4


# ---------------------------------------------------------------------------
# TestRoundtripAllSamples — serialize → write → read → deserialize
# ---------------------------------------------------------------------------


class TestRoundtripAllSamples:
    @pytest.fixture(
        params=sorted(_SAMPLE_DIRS.keys()),
        ids=lambda k: k,
    )
    def sample_name(self, request) -> str:
        return request.param

    @pytest.fixture
    def roundtripped(self, sample_name) -> tuple[Report, Report]:
        return _roundtrip(sample_name)

    def test_roundtrip_succeeds(self, roundtripped):
        original, reread = roundtripped
        assert reread is not None

    def test_page_count_preserved(self, roundtripped):
        original, reread = roundtripped
        assert len(reread.definition.pages) == len(original.definition.pages)

    def test_total_visual_count_preserved(self, roundtripped):
        original, reread = roundtripped
        orig_count = sum(len(p.visuals) for p in original.definition.pages)
        reread_count = sum(len(p.visuals) for p in reread.definition.pages)
        assert reread_count == orig_count

    def test_total_mobile_count_preserved(self, roundtripped):
        original, reread = roundtripped
        orig_count = sum(len(p.mobile_states) for p in original.definition.pages)
        reread_count = sum(len(p.mobile_states) for p in reread.definition.pages)
        assert reread_count == orig_count

    def test_bookmark_count_preserved(self, roundtripped):
        original, reread = roundtripped
        assert len(reread.definition.bookmarks) == len(original.definition.bookmarks)

    def test_page_names_preserved(self, roundtripped):
        original, reread = roundtripped
        orig_names = {getattr(p.page, "name") for p in original.definition.pages}
        reread_names = {getattr(p.page, "name") for p in reread.definition.pages}
        assert reread_names == orig_names

    def test_bookmark_names_preserved(self, roundtripped):
        original, reread = roundtripped
        orig_names = {b.name for b in original.definition.bookmarks}
        reread_names = {b.name for b in reread.definition.bookmarks}
        assert reread_names == orig_names

    def test_version_preserved(self, roundtripped):
        original, reread = roundtripped
        assert reread.definition.version.version == original.definition.version.version

    def test_platform_preserved(self, roundtripped):
        original, reread = roundtripped
        assert (
            reread.platform.metadata.displayName
            == original.platform.metadata.displayName
        )


# ---------------------------------------------------------------------------
# TestRoundtripAIDetails — detailed property comparison
# ---------------------------------------------------------------------------


class TestRoundtripAIDetails:
    @pytest.fixture(scope="class")
    def roundtripped(self) -> tuple[Report, Report]:
        return _roundtrip("ai")

    def test_visuals_per_page_preserved(self, roundtripped):
        original, reread = roundtripped
        orig_by_page = {
            getattr(p.page, "name"): len(p.visuals) for p in original.definition.pages
        }
        reread_by_page = {
            getattr(p.page, "name"): len(p.visuals) for p in reread.definition.pages
        }
        assert reread_by_page == orig_by_page

    def test_mobile_states_per_page_preserved(self, roundtripped):
        original, reread = roundtripped
        orig_by_page = {
            getattr(p.page, "name"): set(p.mobile_states.keys())
            for p in original.definition.pages
        }
        reread_by_page = {
            getattr(p.page, "name"): set(p.mobile_states.keys())
            for p in reread.definition.pages
        }
        assert reread_by_page == orig_by_page

    def test_visual_names_per_page_preserved(self, roundtripped):
        original, reread = roundtripped
        for orig_page in original.definition.pages:
            page_name = getattr(orig_page.page, "name")
            reread_page = next(
                p
                for p in reread.definition.pages
                if getattr(p.page, "name") == page_name
            )
            orig_vis_names = {getattr(v, "name") for v in orig_page.visuals}
            reread_vis_names = {getattr(v, "name") for v in reread_page.visuals}
            assert reread_vis_names == orig_vis_names, (
                f"Visual names differ for page {page_name}"
            )

    def test_static_resources_preserved(self, roundtripped):
        original, reread = roundtripped
        orig_static = getattr(original, "_static_resources", [])
        reread_static = getattr(reread, "_static_resources", [])
        orig_paths = {p.path for p in orig_static}
        reread_paths = {p.path for p in reread_static}
        assert reread_paths == orig_paths


# ---------------------------------------------------------------------------
# TestSerializePartPaths — verify file paths match on-disk structure
# ---------------------------------------------------------------------------


class TestSerializePartPaths:
    @pytest.fixture(scope="class")
    def parts(self) -> list:
        transport = LocalTransport()
        strategy = PbirStrategy()
        disk_parts = transport.read_parts(str(_SAMPLE_DIRS["supply-chain"]))
        report = strategy.deserialize(disk_parts)
        return strategy.serialize(report)

    def test_version_path(self, parts):
        paths = {p.path for p in parts}
        assert "definition/version.json" in paths

    def test_report_path(self, parts):
        paths = {p.path for p in parts}
        assert "definition/report.json" in paths

    def test_pages_metadata_path(self, parts):
        paths = {p.path for p in parts}
        assert "definition/pages/pages.json" in paths

    def test_page_paths_are_nested(self, parts):
        page_paths = [p.path for p in parts if p.path.endswith("/page.json")]
        assert len(page_paths) == 4
        for path in page_paths:
            assert path.startswith("definition/pages/")

    def test_visual_paths_are_nested(self, parts):
        visual_paths = [p.path for p in parts if p.path.endswith("/visual.json")]
        assert len(visual_paths) == 23
        for path in visual_paths:
            assert "/visuals/" in path

    def test_bookmark_paths(self, parts):
        bm_paths = [p.path for p in parts if ".bookmark.json" in p.path]
        assert len(bm_paths) == 4
        for path in bm_paths:
            assert path.startswith("definition/bookmarks/")

    def test_serialized_json_is_valid(self, parts):
        json_parts = [
            p
            for p in parts
            if p.path.endswith(".json") and not p.path.startswith("StaticResources")
        ]
        for part in json_parts:
            data = json.loads(part.payload)
            assert isinstance(data, dict), f"{part.path} is not a JSON object"
