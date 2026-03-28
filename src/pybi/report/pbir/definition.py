from pydantic import BaseModel, Field

from .types import (
    AnyBookmark,
    AnyBookmarksMetadata,
    AnyPagesMetadata,
    AnyReportExtension,
    AnyReport,
    AnyVersion,
    PbirPageWithVisuals,
)


class PbirReportDefinition(BaseModel):
    version: AnyVersion | None = None
    report: AnyReport | None = None
    pages_metadata: AnyPagesMetadata | None = None
    pages: list[PbirPageWithVisuals] = Field(default_factory=list)
    bookmarks_metadata: AnyBookmarksMetadata | None = None
    bookmarks: list[AnyBookmark] = Field(default_factory=list)
    report_extensions: AnyReportExtension | None = None
