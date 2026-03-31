import json
import re
from collections import defaultdict

from pydantic import BaseModel

from ..types import Part
from ...report.report import Report
from ...report.pbir.definition import PbirReportDefinition
from ...report.pbir.types import PbirPageWithVisuals
from ...report.pbir.dispatcher import init_model
from ...report.pbir.models.versionmetadata.model import PbirVersion
from ...report.pbir.models.report.model import PbirReport
from ...report.pbir.models.pagesmetadata.model import PbirPagesMetadata
from ...report.pbir.models.page.model import PbirPage
from ...report.pbir.models.visualcontainer.model import PbirVisualContainer
from ...report.pbir.models.visualcontainermobilestate.model import (
    PbirVisualContainerMobileState,
)
from ...report.pbir.models.bookmarksmetadata.model import PbirBookmarksMetadata
from ...report.pbir.models.bookmark.model import PbirBookmark
from ...report.pbir.models.reportextension.model import PbirReportExtension
from ...fabric.fabric import (
    DefinitionPbir,
    Platform,
    default_definition_pbir,
    default_report_platform,
)
from .helpers import to_part, from_parts

# PbirPageWithVisuals and PbirReportDefinition use TYPE_CHECKING-guarded
# forward references (e.g. "PageV210", "VisualContainerV270").  We import
# all versioned models under their aliased names and inject them into the
# ``types`` module namespace so pydantic can resolve the annotations.
from ...report.pbir import types as _pbir_types
from ...report.pbir.models.versionmetadata.v1_0_0 import (
    VersionMetadata as VersionMetadataV100,
)  # noqa: F401
from ...report.pbir.models.report.v3_0_0 import Report as ReportV300  # noqa: F401
from ...report.pbir.models.report.v3_1_0 import Report as ReportV310  # noqa: F401
from ...report.pbir.models.report.v3_2_0 import Report as ReportV320  # noqa: F401
from ...report.pbir.models.page.v1_4_0 import Page as PageV140  # noqa: F401
from ...report.pbir.models.page.v2_0_0 import Page as PageV200  # noqa: F401
from ...report.pbir.models.page.v2_1_0 import Page as PageV210  # noqa: F401
from ...report.pbir.models.pagesmetadata.v1_0_0 import (
    PagesMetadata as PagesMetadataV100,
)  # noqa: F401
from ...report.pbir.models.bookmark.v1_4_0 import Bookmark as BookmarkV140  # noqa: F401
from ...report.pbir.models.bookmark.v2_0_0 import Bookmark as BookmarkV200  # noqa: F401
from ...report.pbir.models.bookmark.v2_1_0 import Bookmark as BookmarkV210  # noqa: F401
from ...report.pbir.models.bookmarksmetadata.v1_0_0 import (
    BookmarksMetadata as BookmarkMetadataV100,
)  # noqa: F401
from ...report.pbir.models.reportextension.v1_0_0 import (
    ReportExtension as ReportExtensionV100,
)  # noqa: F401
from ...report.pbir.models.visualcontainermobilestate.v2_2_0 import (
    VisualContainerMobileState as VisualContainerMobileStateV220,
)  # noqa: F401
from ...report.pbir.models.visualcontainer.v2_3_0 import (
    VisualContainer as VisualContainerV230,
)  # noqa: F401
from ...report.pbir.models.visualcontainer.v2_4_0 import (
    VisualContainer as VisualContainerV240,
)  # noqa: F401
from ...report.pbir.models.visualcontainer.v2_5_0 import (
    VisualContainer as VisualContainerV250,
)  # noqa: F401
from ...report.pbir.models.visualcontainer.v2_6_0 import (
    VisualContainer as VisualContainerV260,
)  # noqa: F401
from ...report.pbir.models.visualcontainer.v2_7_0 import (
    VisualContainer as VisualContainerV270,
)  # noqa: F401

_ALIAS_NAMES = [
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
]
_this_globals = globals()
for _name in _ALIAS_NAMES:
    setattr(_pbir_types, _name, _this_globals[_name])

PbirPageWithVisuals.model_rebuild()
PbirReportDefinition.model_rebuild()

_VERSION_PATH = "definition/version.json"
_REPORT_PATH = "definition/report.json"
_PAGES_METADATA_PATH = "definition/pages/pages.json"
_BOOKMARKS_METADATA_PATH = "definition/bookmarks/bookmarks.json"
_REPORT_EXTENSIONS_PATH = "definition/reportExtensions.json"

_PAGE_RE = re.compile(r"^definition/pages/([^/]+)/page\.json$")
_VISUAL_RE = re.compile(r"^definition/pages/([^/]+)/visuals/([^/]+)/visual\.json$")
_MOBILE_RE = re.compile(r"^definition/pages/([^/]+)/visuals/([^/]+)/mobile\.json$")
_BOOKMARK_RE = re.compile(r"^definition/bookmarks/([^/]+)\.bookmark\.json$")


def _get_name(model: BaseModel) -> str:
    name = getattr(model, "name", None)
    if not name:
        raise ValueError(
            f"Cannot serialize {type(model).__name__}: missing 'name' field."
        )
    return name


class PbirStrategy:
    def serialize(self, model: Report) -> list[Part]:
        if not isinstance(model.definition, PbirReportDefinition):
            raise ValueError("Report definition is not PBIR format.")

        parts: list[Part] = []
        defn = model.definition

        if defn.version is not None:
            parts.append(to_part(defn.version, _VERSION_PATH))

        if defn.report is not None:
            parts.append(to_part(defn.report, _REPORT_PATH))

        if defn.pages_metadata is not None:
            parts.append(to_part(defn.pages_metadata, _PAGES_METADATA_PATH))

        for page_with_visuals in defn.pages:
            page_name = _get_name(page_with_visuals.page)
            parts.append(
                to_part(
                    page_with_visuals.page,
                    f"definition/pages/{page_name}/page.json",
                )
            )

            for visual in page_with_visuals.visuals:
                visual_name = _get_name(visual)
                parts.append(
                    to_part(
                        visual,
                        f"definition/pages/{page_name}/visuals/{visual_name}/visual.json",
                    )
                )

            for visual_name, mobile_state in page_with_visuals.mobile_states.items():
                parts.append(
                    to_part(
                        mobile_state,
                        f"definition/pages/{page_name}/visuals/{visual_name}/mobile.json",
                    )
                )

        if defn.bookmarks_metadata is not None:
            parts.append(to_part(defn.bookmarks_metadata, _BOOKMARKS_METADATA_PATH))

        for bookmark in defn.bookmarks:
            bookmark_name = _get_name(bookmark)
            parts.append(
                to_part(
                    bookmark,
                    f"definition/bookmarks/{bookmark_name}.bookmark.json",
                )
            )

        if defn.report_extensions is not None:
            parts.append(to_part(defn.report_extensions, _REPORT_EXTENSIONS_PATH))

        parts.append(to_part(model.platform))
        parts.append(to_part(model.item_definition))

        static = getattr(model, "_static_resources", None)
        if static:
            parts.extend(static)

        return parts

    def deserialize(self, parts: list[Part]) -> Report:
        version = None
        report_metadata = None
        pages_metadata = None
        bookmarks_metadata = None
        report_extensions = None

        pages_map: dict[str, BaseModel] = {}
        visuals_map: dict[str, list[BaseModel]] = defaultdict(list)
        mobiles_map: dict[str, dict[str, BaseModel]] = defaultdict(dict)
        bookmarks: list[BaseModel] = []

        for part in parts:
            path = part.path

            if path == _VERSION_PATH:
                version = init_model(
                    json.loads(part.payload), "versionMetadata", PbirVersion
                )
                continue

            if path == _REPORT_PATH:
                report_metadata = init_model(
                    json.loads(part.payload), "report", PbirReport
                )
                continue

            if path == _PAGES_METADATA_PATH:
                pages_metadata = init_model(
                    json.loads(part.payload), "pagesMetadata", PbirPagesMetadata
                )
                continue

            if path == _BOOKMARKS_METADATA_PATH:
                bookmarks_metadata = init_model(
                    json.loads(part.payload),
                    "bookmarksMetadata",
                    PbirBookmarksMetadata,
                )
                continue

            if path == _REPORT_EXTENSIONS_PATH:
                report_extensions = init_model(
                    json.loads(part.payload), "reportExtension", PbirReportExtension
                )
                continue

            m = _PAGE_RE.match(path)
            if m:
                pages_map[m.group(1)] = init_model(
                    json.loads(part.payload), "page", PbirPage
                )
                continue

            m = _VISUAL_RE.match(path)
            if m:
                visuals_map[m.group(1)].append(
                    init_model(
                        json.loads(part.payload),
                        "visualContainer",
                        PbirVisualContainer,
                    )
                )
                continue

            m = _MOBILE_RE.match(path)
            if m:
                mobiles_map[m.group(1)][m.group(2)] = init_model(
                    json.loads(part.payload),
                    "visualContainerMobileState",
                    PbirVisualContainerMobileState,
                )
                continue

            m = _BOOKMARK_RE.match(path)
            if m:
                bookmarks.append(
                    init_model(json.loads(part.payload), "bookmark", PbirBookmark)
                )
                continue

        pages = [
            PbirPageWithVisuals(
                page=page,
                visuals=visuals_map.get(page_name, []),
                mobile_states=mobiles_map.get(page_name, {}),
            )
            for page_name, page in pages_map.items()
        ]

        definition = PbirReportDefinition(
            version=version,
            report_metadata=report_metadata,
            pages_metadata=pages_metadata,
            pages=pages,
            bookmarks_metadata=bookmarks_metadata,
            bookmarks=bookmarks,
            report_extensions=report_extensions,
        )

        platform = from_parts(parts, Platform) or default_report_platform()
        item_definition = from_parts(parts, DefinitionPbir) or default_definition_pbir()

        report = Report(
            item_definition=item_definition,
            definition=definition,
            platform=platform,
        )

        static = [
            p
            for p in parts
            if p.path.startswith("StaticResources/")
            or p.path.startswith("staticResources/")
        ]
        if static:
            object.__setattr__(report, "_static_resources", static)

        return report
