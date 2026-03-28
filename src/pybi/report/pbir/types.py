from typing import TYPE_CHECKING, Union

from pydantic import BaseModel, Field


if TYPE_CHECKING:
    from .models.versionmetadata.v1_0_0 import VersionMetadata as VersionMetadataV100
    from .models.report.v3_0_0 import Report as ReportV300
    from .models.report.v3_1_0 import Report as ReportV310
    from .models.report.v3_2_0 import Report as ReportV320
    from .models.page.v1_4_0 import Page as PageV140
    from .models.page.v2_0_0 import Page as PageV200
    from .models.page.v2_1_0 import Page as PageV210
    from .models.pagesmetadata.v1_0_0 import PagesMetadata as PagesMetadataV100
    from .models.bookmark.v1_4_0 import Bookmark as BookmarkV140
    from .models.bookmark.v2_0_0 import Bookmark as BookmarkV200
    from .models.bookmark.v2_1_0 import Bookmark as BookmarkV210
    from .models.bookmarksmetadata.v1_0_0 import (
        BookmarksMetadata as BookmarkMetadataV100,
    )
    from .models.reportextension.v1_0_0 import ReportExtension as ReportExtensionV100
    from .models.visualcontainermobilestate.v2_2_0 import (
        VisualContainerMobileState as VisualContainerMobileStateV220,
    )
    from .models.visualcontainer.v2_3_0 import VisualContainer as VisualContainerV230
    from .models.visualcontainer.v2_4_0 import VisualContainer as VisualContainerV240
    from .models.visualcontainer.v2_5_0 import VisualContainer as VisualContainerV250
    from .models.visualcontainer.v2_6_0 import VisualContainer as VisualContainerV260
    from .models.visualcontainer.v2_7_0 import VisualContainer as VisualContainerV270

from .models.versionmetadata.model import PbirVersion
from .models.bookmark.model import PbirBookmark
from .models.report.model import PbirReport
from .models.page.model import PbirPage
from .models.pagesmetadata.model import PbirPagesMetadata
from .models.bookmarksmetadata.model import PbirBookmarksMetadata
from .models.reportextension.model import PbirReportExtension
from .models.visualcontainermobilestate.model import PbirVisualContainerMobileState
from .models.visualcontainer.model import PbirVisualContainer


AnyVersion = Union[PbirVersion, "VersionMetadataV100"]
AnyBookmark = Union[PbirBookmark, "BookmarkV210", "BookmarkV200", "BookmarkV140"]
AnyReport = Union[PbirReport, "ReportV320", "ReportV310", "ReportV300"]
AnyPage = Union[PbirPage, "PageV210", "PageV200", "PageV140"]
AnyPagesMetadata = Union[PbirPagesMetadata, "PagesMetadataV100"]
AnyBookmarksMetadata = Union[PbirBookmarksMetadata, "BookmarkMetadataV100"]
AnyReportExtension = Union[PbirReportExtension, "ReportExtensionV100"]
AnyMobileState = Union[PbirVisualContainerMobileState, "VisualContainerMobileStateV220"]
AnyVisualContainer = Union[
    PbirVisualContainer,
    "VisualContainerV270",
    "VisualContainerV260",
    "VisualContainerV250",
    "VisualContainerV240",
    "VisualContainerV230",
]


class PbirPageWithVisuals(BaseModel):
    page: AnyPage
    visuals: list[AnyVisualContainer] = Field(default_factory=list)
    mobile_states: dict[str, AnyMobileState] = Field(default_factory=dict)
