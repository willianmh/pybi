"""Unit tests for PbirStrategy serialize / deserialize."""

import json

import pytest
from pydantic import BaseModel

# The Union types in ``types.py`` use TYPE_CHECKING forward references with
# aliased names (e.g. ``PageV210``).  We must inject every alias into the
# module namespace so that ``model_rebuild()`` can resolve them.
from pybi.report.pbir import types as _pbir_types

from pybi.report.pbir.models.versionmetadata.v1_0_0 import (
    VersionMetadata as VersionMetadataV100,
)  # noqa: F401
from pybi.report.pbir.models.report.v3_0_0 import Report as ReportV300  # noqa: F401
from pybi.report.pbir.models.report.v3_1_0 import Report as ReportV310  # noqa: F401
from pybi.report.pbir.models.report.v3_2_0 import Report as ReportV320  # noqa: F401
from pybi.report.pbir.models.page.v1_4_0 import Page as PageV140  # noqa: F401
from pybi.report.pbir.models.page.v2_0_0 import Page as PageV200  # noqa: F401
from pybi.report.pbir.models.page.v2_1_0 import Page as PageV210  # noqa: F401
from pybi.report.pbir.models.pagesmetadata.v1_0_0 import (
    PagesMetadata as PagesMetadataV100,
)  # noqa: F401
from pybi.report.pbir.models.bookmark.v1_4_0 import Bookmark as BookmarkV140  # noqa: F401
from pybi.report.pbir.models.bookmark.v2_0_0 import Bookmark as BookmarkV200  # noqa: F401
from pybi.report.pbir.models.bookmark.v2_1_0 import Bookmark as BookmarkV210  # noqa: F401
from pybi.report.pbir.models.bookmarksmetadata.v1_0_0 import (
    BookmarksMetadata as BookmarkMetadataV100,
)  # noqa: F401
from pybi.report.pbir.models.reportextension.v1_0_0 import (
    ReportExtension as ReportExtensionV100,
)  # noqa: F401
from pybi.report.pbir.models.visualcontainermobilestate.v2_2_0 import (
    VisualContainerMobileState as VisualContainerMobileStateV220,
)  # noqa: F401
from pybi.report.pbir.models.visualcontainer.v2_3_0 import (
    VisualContainer as VisualContainerV230,
)  # noqa: F401
from pybi.report.pbir.models.visualcontainer.v2_4_0 import (
    VisualContainer as VisualContainerV240,
)  # noqa: F401
from pybi.report.pbir.models.visualcontainer.v2_5_0 import (
    VisualContainer as VisualContainerV250,
)  # noqa: F401
from pybi.report.pbir.models.visualcontainer.v2_6_0 import (
    VisualContainer as VisualContainerV260,
)  # noqa: F401
from pybi.report.pbir.models.visualcontainer.v2_7_0 import (
    VisualContainer as VisualContainerV270,
)  # noqa: F401

# Inject all aliases into the types module namespace
for _name in [
    "VersionMetadataV100",
    "ReportV300",
    "ReportV310",
    "ReportV320",
    "PageV140",
    "PageV200",
    "PageV210",
    "PagesMetadataV100",
    "BookmarkV140",
    "BookmarkV200",
    "BookmarkV210",
    "BookmarkMetadataV100",
    "ReportExtensionV100",
    "VisualContainerMobileStateV220",
    "VisualContainerV230",
    "VisualContainerV240",
    "VisualContainerV250",
    "VisualContainerV260",
    "VisualContainerV270",
]:
    setattr(_pbir_types, _name, globals()[_name])

_pbir_types.PbirPageWithVisuals.model_rebuild()

from pybi.report.pbir.definition import PbirReportDefinition

PbirReportDefinition.model_rebuild()

from pybi.serialization.types import Part
from pybi.serialization.strategies.pbir import (
    PbirStrategy,
    _get_name,
    to_part,
    _VERSION_PATH,
    _REPORT_PATH,
    _PAGES_METADATA_PATH,
    _BOOKMARKS_METADATA_PATH,
    _REPORT_EXTENSIONS_PATH,
)
from pybi.report.report import Report
from pybi.report.pbir.definition import PbirReportDefinition
from pybi.report.pbir.types import PbirPageWithVisuals
from pybi.report.pbir.models.versionmetadata.model import PbirVersion
from pybi.report.pbir.models.report.model import PbirReport
from pybi.report.pbir.models.pagesmetadata.model import PbirPagesMetadata
from pybi.report.pbir.models.page.model import PbirPage
from pybi.report.pbir.models.visualcontainer.model import PbirVisualContainer
from pybi.report.pbir.models.visualcontainermobilestate.model import (
    PbirVisualContainerMobileState,
)
from pybi.report.pbir.models.bookmarksmetadata.model import PbirBookmarksMetadata
from pybi.report.pbir.models.bookmark.model import PbirBookmark
from pybi.report.pbir.models.reportextension.model import PbirReportExtension
from pybi.report.legacy.legacy_model import ReportJsonDefinition
from pybi.fabric.fabric import (
    DefinitionPbir,
    Platform,
    default_definition_pbir,
    default_report_platform,
)
from pybi.serialization.strategies.helpers import find_part


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _json_part(path: str, data: dict) -> Part:
    return Part(path=path, payload=json.dumps(data).encode())


def _make_version(version: str = "2.0.0") -> PbirVersion:
    return PbirVersion.model_validate({"version": version})


def _make_report_metadata() -> PbirReport:
    return PbirReport.model_validate(
        {"$schema": "https://example.com/report/3.0.0/schema.json"}
    )


def _make_pages_metadata(page_names: list[str]) -> PbirPagesMetadata:
    return PbirPagesMetadata.model_validate(
        {"pageOrder": page_names, "activePageName": page_names[0]}
    )


def _make_page(name: str, display_name: str = "Page 1") -> PbirPage:
    return PbirPage.model_validate(
        {"name": name, "displayName": display_name, "width": 1280, "height": 720}
    )


def _make_visual(name: str) -> PbirVisualContainer:
    return PbirVisualContainer.model_validate(
        {
            "name": name,
            "position": {"x": 0, "y": 0, "z": 0, "width": 100, "height": 100},
        }
    )


def _make_mobile_state() -> PbirVisualContainerMobileState:
    return PbirVisualContainerMobileState.model_validate(
        {"position": {"x": 10, "y": 10, "z": 0, "width": 50, "height": 50}}
    )


def _make_bookmark(name: str, display_name: str = "Bookmark") -> PbirBookmark:
    return PbirBookmark.model_validate({"name": name, "displayName": display_name})


def _make_bookmarks_metadata(names: list[str]) -> PbirBookmarksMetadata:
    return PbirBookmarksMetadata.model_validate({"items": [{"name": n} for n in names]})


def _make_report_extension() -> PbirReportExtension:
    return PbirReportExtension.model_validate({"name": "TestExtension", "entities": []})


def _make_report(
    defn: PbirReportDefinition,
    platform: Platform | None = None,
    item_def: DefinitionPbir | None = None,
) -> Report:
    return Report(
        raw_definition=defn,
        platform=platform or default_report_platform(),
        item_definition=item_def or default_definition_pbir(),
    )


# ---------------------------------------------------------------------------
# TestGetName
# ---------------------------------------------------------------------------


class TestGetName:
    def test_declared_field(self):
        bookmark = PbirBookmark(name="bm1", displayName="Bookmark 1")
        assert _get_name(bookmark) == "bm1"

    def test_extra_field(self):
        page = PbirPage.model_validate({"name": "page1"})
        assert _get_name(page) == "page1"

    def test_missing_name_raises(self):
        page = PbirPage.model_validate({})
        with pytest.raises(ValueError, match="missing 'name' field"):
            _get_name(page)

    def test_empty_name_raises(self):
        bookmark = PbirBookmark(name="", displayName="")
        with pytest.raises(ValueError, match="missing 'name' field"):
            _get_name(bookmark)


# ---------------------------------------------------------------------------
# TestSerializeModel
# ---------------------------------------------------------------------------


class TestSerializeModel:
    def test_produces_correct_path(self):
        version = _make_version()
        part = to_part(version, "definition/version.json")
        assert part.path == "definition/version.json"

    def test_produces_valid_json(self):
        version = _make_version("3.0.0")
        part = to_part(version, "some/path.json")
        data = json.loads(part.payload)
        assert data["version"] == "3.0.0"

    def test_alias_serialization(self):
        report = PbirReport.model_validate(
            {"$schema": "https://example.com/report/3.0.0/schema.json"}
        )
        part = to_part(report, "test.json")
        data = json.loads(part.payload)
        assert "$schema" in data
        assert "field_schema" not in data


# ---------------------------------------------------------------------------
# TestSerializeMinimal
# ---------------------------------------------------------------------------


class TestSerializeMinimal:
    """Serialize a PbirReportDefinition with all fields None/empty."""

    def test_empty_definition(self):
        defn = PbirReportDefinition()
        report = _make_report(defn)
        strategy = PbirStrategy()
        parts = strategy.serialize(report)

        paths = {p.path for p in parts}
        assert ".platform" in paths
        assert "definition.pbir" in paths
        # No definition/* files since everything is None/empty
        definition_paths = {p for p in paths if p.startswith("definition/")}
        assert len(definition_paths) == 0


class TestSerializeRejectsNonPbir:
    def test_raises_for_legacy_definition(self):
        legacy_def = ReportJsonDefinition.model_validate(
            {"config": "{}", "layoutOptimization": 0}
        )
        report = Report(
            raw_definition=legacy_def,
            platform=default_report_platform(),
            item_definition=default_definition_pbir(),
        )
        strategy = PbirStrategy()
        with pytest.raises(ValueError, match="not PBIR format"):
            strategy.serialize(report)


# ---------------------------------------------------------------------------
# TestSerializeFull
# ---------------------------------------------------------------------------


class TestSerializeFull:
    @pytest.fixture
    def report(self) -> Report:
        page = _make_page("Page1")
        visual1 = _make_visual("vis1")
        visual2 = _make_visual("vis2")
        mobile = _make_mobile_state()

        pages = [
            PbirPageWithVisuals(
                page=page,
                visuals=[visual1, visual2],
                mobile_states={"vis1": mobile},
            )
        ]
        bookmark = _make_bookmark("bm1", "My Bookmark")
        defn = PbirReportDefinition(
            version=_make_version(),
            report=_make_report_metadata(),
            pages_metadata=_make_pages_metadata(["Page1"]),
            pages=pages,
            bookmarks_metadata=_make_bookmarks_metadata(["bm1"]),
            bookmarks=[bookmark],
            report_extensions=_make_report_extension(),
        )
        return _make_report(defn)

    @pytest.fixture
    def parts(self, report) -> list[Part]:
        return PbirStrategy().serialize(report)

    @pytest.fixture
    def paths(self, parts) -> set[str]:
        return {p.path for p in parts}

    def test_version_present(self, paths):
        assert _VERSION_PATH in paths

    def test_report_present(self, paths):
        assert _REPORT_PATH in paths

    def test_pages_metadata_present(self, paths):
        assert _PAGES_METADATA_PATH in paths

    def test_page_file(self, paths):
        assert "definition/pages/Page1/page.json" in paths

    def test_visual_files(self, paths):
        assert "definition/pages/Page1/visuals/vis1/visual.json" in paths
        assert "definition/pages/Page1/visuals/vis2/visual.json" in paths

    def test_mobile_state_file(self, paths):
        assert "definition/pages/Page1/visuals/vis1/mobile.json" in paths

    def test_no_mobile_for_vis2(self, paths):
        assert "definition/pages/Page1/visuals/vis2/mobile.json" not in paths

    def test_bookmarks_metadata_present(self, paths):
        assert _BOOKMARKS_METADATA_PATH in paths

    def test_bookmark_file(self, paths):
        assert "definition/bookmarks/bm1.bookmark.json" in paths

    def test_report_extensions_present(self, paths):
        assert _REPORT_EXTENSIONS_PATH in paths

    def test_platform_present(self, paths):
        assert ".platform" in paths

    def test_definition_pbir_present(self, paths):
        assert "definition.pbir" in paths

    def test_page_json_content(self, parts):
        part = find_part(parts, "definition/pages/Page1/page.json")
        data = json.loads(part.payload)
        assert data["name"] == "Page1"
        assert data["displayName"] == "Page 1"

    def test_visual_json_content(self, parts):
        part = find_part(parts, "definition/pages/Page1/visuals/vis1/visual.json")
        data = json.loads(part.payload)
        assert data["name"] == "vis1"
        assert data["position"]["width"] == 100

    def test_bookmark_json_content(self, parts):
        part = find_part(parts, "definition/bookmarks/bm1.bookmark.json")
        data = json.loads(part.payload)
        assert data["name"] == "bm1"
        assert data["displayName"] == "My Bookmark"


# ---------------------------------------------------------------------------
# TestSerializeStaticResources
# ---------------------------------------------------------------------------


class TestSerializeStaticResources:
    def test_static_resources_passthrough(self):
        defn = PbirReportDefinition()
        report = _make_report(defn)
        static = [
            Part(path="StaticResources/theme.json", payload=b"{}"),
            Part(path="StaticResources/image.png", payload=b"\x89PNG"),
        ]
        object.__setattr__(report, "_static_resources", static)

        parts = PbirStrategy().serialize(report)
        paths = {p.path for p in parts}
        assert "StaticResources/theme.json" in paths
        assert "StaticResources/image.png" in paths


# ---------------------------------------------------------------------------
# TestDeserializeMinimal
# ---------------------------------------------------------------------------


class TestDeserializeMinimal:
    def test_empty_parts_creates_defaults(self):
        parts = [
            _json_part(
                "definition.pbir",
                {"version": "4.0", "datasetReference": {"byPath": {"path": ".."}}},
            ),
            _json_part(
                ".platform",
                {"metadata": {"type": "Report", "displayName": "Test"}},
            ),
        ]
        report = PbirStrategy().deserialize(parts)
        assert isinstance(report.raw_definition, PbirReportDefinition)
        defn = report.raw_definition
        assert defn.version is None
        assert defn.report is None
        assert defn.pages_metadata is None
        assert defn.pages == []
        assert defn.bookmarks_metadata is None
        assert defn.bookmarks == []
        assert defn.report_extensions is None


# ---------------------------------------------------------------------------
# TestDeserializeFull
# ---------------------------------------------------------------------------


class TestDeserializeFull:
    @pytest.fixture
    def parts(self) -> list[Part]:
        return [
            _json_part(
                "definition.pbir",
                {"version": "4.0", "datasetReference": {"byPath": {"path": ".."}}},
            ),
            _json_part(
                ".platform",
                {"metadata": {"type": "Report", "displayName": "Test"}},
            ),
            _json_part(_VERSION_PATH, {"version": "2.0.0"}),
            _json_part(
                _REPORT_PATH,
                {"$schema": "https://example.com/report/3.0.0/schema.json"},
            ),
            _json_part(
                _PAGES_METADATA_PATH,
                {"pageOrder": ["pg1", "pg2"], "activePageName": "pg1"},
            ),
            _json_part(
                "definition/pages/pg1/page.json",
                {"name": "pg1", "displayName": "First"},
            ),
            _json_part(
                "definition/pages/pg2/page.json",
                {"name": "pg2", "displayName": "Second"},
            ),
            _json_part(
                "definition/pages/pg1/visuals/v1/visual.json",
                {
                    "name": "v1",
                    "position": {"x": 0, "y": 0, "z": 0, "width": 100, "height": 50},
                },
            ),
            _json_part(
                "definition/pages/pg1/visuals/v2/visual.json",
                {
                    "name": "v2",
                    "position": {"x": 100, "y": 0, "z": 1, "width": 200, "height": 50},
                },
            ),
            _json_part(
                "definition/pages/pg1/visuals/v1/mobile.json",
                {"position": {"x": 5, "y": 5, "z": 0, "width": 50, "height": 50}},
            ),
            _json_part(
                _BOOKMARKS_METADATA_PATH,
                {"items": [{"name": "bk1"}]},
            ),
            _json_part(
                "definition/bookmarks/bk1.bookmark.json",
                {"name": "bk1", "displayName": "Bookmark One"},
            ),
            _json_part(
                _REPORT_EXTENSIONS_PATH,
                {"name": "ext1"},
            ),
            Part(path="StaticResources/theme.json", payload=b"{}"),
        ]

    @pytest.fixture
    def report(self, parts) -> Report:
        return PbirStrategy().deserialize(parts)

    @pytest.fixture
    def defn(self, report) -> PbirReportDefinition:
        return report.raw_definition

    def test_report_type(self, report):
        assert isinstance(report.raw_definition, PbirReportDefinition)

    def test_version(self, defn):
        assert defn.version is not None
        assert defn.version.version == "2.0.0"

    def test_report_metadata(self, defn):
        assert defn.report is not None

    def test_pages_metadata(self, defn):
        assert defn.pages_metadata is not None

    def test_page_count(self, defn):
        assert len(defn.pages) == 2

    def test_page_names(self, defn):
        names = {getattr(p.page, "name") for p in defn.pages}
        assert names == {"pg1", "pg2"}

    def test_visuals_grouped_under_page(self, defn):
        pg1 = next(p for p in defn.pages if getattr(p.page, "name") == "pg1")
        assert len(pg1.visuals) == 2

    def test_pg2_has_no_visuals(self, defn):
        pg2 = next(p for p in defn.pages if getattr(p.page, "name") == "pg2")
        assert len(pg2.visuals) == 0

    def test_mobile_state_grouped(self, defn):
        pg1 = next(p for p in defn.pages if getattr(p.page, "name") == "pg1")
        assert "v1" in pg1.mobile_states
        assert "v2" not in pg1.mobile_states

    def test_bookmarks_metadata(self, defn):
        assert defn.bookmarks_metadata is not None

    def test_bookmark_count(self, defn):
        assert len(defn.bookmarks) == 1
        assert defn.bookmarks[0].name == "bk1"

    def test_report_extensions(self, defn):
        assert defn.report_extensions is not None

    def test_platform(self, report):
        assert report.platform is not None

    def test_item_definition(self, report):
        assert report.item_definition is not None

    def test_static_resources(self, report):
        static = getattr(report, "_static_resources", [])
        assert len(static) == 1
        assert static[0].path == "StaticResources/theme.json"


# ---------------------------------------------------------------------------
# TestDeserializeIgnoresUnknownParts
# ---------------------------------------------------------------------------


class TestDeserializeIgnoresUnknownParts:
    def test_unknown_paths_do_not_crash(self):
        parts = [
            _json_part(
                "definition.pbir",
                {"version": "4.0", "datasetReference": {"byPath": {"path": ".."}}},
            ),
            _json_part(
                ".platform",
                {"metadata": {"type": "Report", "displayName": "Test"}},
            ),
            Part(path="unknown/file.txt", payload=b"data"),
            Part(path="definition/unknown.json", payload=b"{}"),
        ]
        report = PbirStrategy().deserialize(parts)
        assert isinstance(report.raw_definition, PbirReportDefinition)


# ---------------------------------------------------------------------------
# TestRoundtrip
# ---------------------------------------------------------------------------


class TestRoundtrip:
    """serialize → deserialize produces equivalent data."""

    @pytest.fixture
    def original(self) -> Report:
        page = _make_page("MainPage")
        vis = _make_visual("chart1")
        mobile = _make_mobile_state()
        bookmark = _make_bookmark("bk_saved", "Saved View")

        defn = PbirReportDefinition(
            version=_make_version("2.0.0"),
            report=_make_report_metadata(),
            pages_metadata=_make_pages_metadata(["MainPage"]),
            pages=[
                PbirPageWithVisuals(
                    page=page,
                    visuals=[vis],
                    mobile_states={"chart1": mobile},
                )
            ],
            bookmarks_metadata=_make_bookmarks_metadata(["bk_saved"]),
            bookmarks=[bookmark],
        )
        return _make_report(defn)

    @pytest.fixture
    def roundtripped(self, original) -> Report:
        strategy = PbirStrategy()
        parts = strategy.serialize(original)
        return strategy.deserialize(parts)

    def test_version_preserved(self, original, roundtripped):
        assert roundtripped.raw_definition.version.version == "2.0.0"

    def test_page_count_preserved(self, original, roundtripped):
        assert len(roundtripped.definition.pages) == len(original.definition.pages)

    def test_page_name_preserved(self, roundtripped):
        page = roundtripped.raw_definition.pages[0]
        assert getattr(page.page, "name") == "MainPage"

    def test_visual_count_preserved(self, roundtripped):
        page = roundtripped.definition.pages[0]
        assert len(page.visuals) == 1

    def test_visual_name_preserved(self, roundtripped):
        vis = roundtripped.definition.pages[0].visuals[0]
        assert getattr(vis, "name") == "chart1"

    def test_mobile_state_preserved(self, roundtripped):
        page = roundtripped.raw_definition.pages[0]
        assert "chart1" in page.mobile_states

    def test_bookmark_preserved(self, roundtripped):
        assert len(roundtripped.definition.bookmarks) == 1
        assert roundtripped.definition.bookmarks[0].name == "bk_saved"

    def test_platform_preserved(self, original, roundtripped):
        assert roundtripped.platform.metadata.type == original.platform.metadata.type

    def test_item_definition_preserved(self, roundtripped):
        assert roundtripped.item_definition is not None


# ---------------------------------------------------------------------------
# TestMultiplePages
# ---------------------------------------------------------------------------


class TestMultiplePages:
    def test_visuals_stay_grouped_with_correct_page(self):
        pages = [
            PbirPageWithVisuals(
                page=_make_page("A"),
                visuals=[_make_visual("a_vis1"), _make_visual("a_vis2")],
            ),
            PbirPageWithVisuals(
                page=_make_page("B"),
                visuals=[_make_visual("b_vis1")],
            ),
        ]
        defn = PbirReportDefinition(pages=pages)
        report = _make_report(defn)

        strategy = PbirStrategy()
        parts = strategy.serialize(report)
        result = strategy.deserialize(parts)

        pages_by_name = {
            getattr(p.page, "name"): p for p in result.raw_definition.pages
        }
        assert len(pages_by_name["A"].visuals) == 2
        assert len(pages_by_name["B"].visuals) == 1


# ---------------------------------------------------------------------------
# TestSchemaDispatch
# ---------------------------------------------------------------------------


class TestSchemaDispatch:
    def test_versioned_model_resolved_for_known_schema(self):
        from pybi.report.pbir.models.versionmetadata.v1_0_0 import (
            VersionMetadata as VersionMetadataV100,
        )

        parts = [
            _json_part(
                "definition.pbir",
                {"version": "4.0", "datasetReference": {"byPath": {"path": ".."}}},
            ),
            _json_part(
                ".platform",
                {"metadata": {"type": "Report", "displayName": "Test"}},
            ),
            _json_part(
                _VERSION_PATH,
                {
                    "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json",
                    "version": "2.0.0",
                },
            ),
        ]
        report = PbirStrategy().deserialize(parts)
        assert isinstance(report.raw_definition.version, VersionMetadataV100)

    def test_fallback_model_for_unknown_schema(self):
        parts = [
            _json_part(
                "definition.pbir",
                {"version": "4.0", "datasetReference": {"byPath": {"path": ".."}}},
            ),
            _json_part(
                ".platform",
                {"metadata": {"type": "Report", "displayName": "Test"}},
            ),
            _json_part(
                _VERSION_PATH,
                {
                    "$schema": "https://example.com/versionMetadata/99.99.99/schema.json",
                    "version": "2.0.0",
                },
            ),
        ]
        report = PbirStrategy().deserialize(parts)
        assert isinstance(report.raw_definition.version, PbirVersion)
