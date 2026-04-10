from pathlib import Path

from pydantic import BaseModel, PrivateAttr

from ..fabric.fabric import Platform, DefinitionPbir
from .legacy.legacy_model import ReportJsonDefinition
from .pbir.definition import PbirReportDefinition
from .pbir.types import AnyBookmark, AnyVisualContainer, PbirPageWithVisuals
from .types import ReportFormat


def _page_display_name(page_with_visuals: PbirPageWithVisuals) -> str | None:
    """Extract the user-facing display name from any versioned page object."""
    return getattr(page_with_visuals.page, "displayName", None)


class Report(BaseModel):
    item_definition: DefinitionPbir
    definition: ReportJsonDefinition | PbirReportDefinition
    platform: Platform

    _ROOT_PATH: str | None = PrivateAttr(default="MyPowerBIDashboard.Report")
    _source_format: ReportFormat | None = PrivateAttr(default=None)

    # - convenience read properties ---------------------─

    @property
    def pages(self) -> list[PbirPageWithVisuals]:
        """All pages in the report (PBIR format only).

        Returns an empty list for legacy ``report.json`` reports.
        Each element is a :class:`~pybi.report.pbir.types.PbirPageWithVisuals`
        containing the page metadata and its list of visuals.
        """
        if isinstance(self.definition, PbirReportDefinition):
            return self.definition.pages
        return []

    def get_page(self, display_name: str) -> PbirPageWithVisuals:
        """Return the page whose ``displayName`` equals *display_name*.

        Raises :class:`~pybi.errors.UnsupportedFormatError` when called on a
        legacy ``report.json`` report (pages are not modelled for that format).
        Raises :class:`~pybi.errors.PageNotFoundError` if no matching page is
        found.
        """
        if not isinstance(self.definition, PbirReportDefinition):
            from ..errors import UnsupportedFormatError

            raise UnsupportedFormatError(
                "get_page() is only supported for PBIR format reports, "
                "not legacy report.json"
            )
        for p in self.pages:
            if _page_display_name(p) == display_name:
                return p
        from ..errors import PageNotFoundError

        raise PageNotFoundError(display_name)

    def find_page(self, display_name: str) -> PbirPageWithVisuals | None:
        """Return the page whose ``displayName`` equals *display_name*, or
        ``None`` if not found."""
        for p in self.pages:
            if _page_display_name(p) == display_name:
                return p
        return None

    @property
    def visuals(self) -> list[AnyVisualContainer]:
        """All visuals across all pages, in page order."""
        return [v for p in self.pages for v in p.visuals]

    @property
    def bookmarks(self) -> list[AnyBookmark]:
        """All bookmarks defined in the report (PBIR format only)."""
        if isinstance(self.definition, PbirReportDefinition):
            return self.definition.bookmarks
        return []

    # - persistence -----------------------------─

    def save(self, format: ReportFormat | None = None) -> None:
        """Write back to the path this report was read from.

        Equivalent to ``report.write(original_path, format)``.  Raises
        ``ValueError`` when the report was not loaded from a path.
        """
        self.write(self._ROOT_PATH, format)

    @classmethod
    def read(cls, root_path: str | Path) -> Report:
        from ..serialization.strategies import PbirStrategy, ReportJsonStrategy
        from ..serialization.transport import LocalTransport
        from ..serialization.detect import detect_report_format

        fmt = detect_report_format(root_path=root_path)
        strategy = PbirStrategy() if fmt is ReportFormat.PBIR else ReportJsonStrategy()
        transport = LocalTransport()

        parts = transport.read_parts(root=root_path)
        report = strategy.deserialize(parts=parts)
        report._ROOT_PATH = str(root_path)
        report._source_format = fmt
        return report

    def write(
        self,
        root_path: str | Path | None,
        format: ReportFormat | None,
    ):
        from ..serialization.strategies import PbirStrategy, ReportJsonStrategy
        from ..serialization.transport import LocalTransport

        root_path = root_path or self._ROOT_PATH
        if not root_path:
            raise ValueError("You must provide a root_path.")

        if format is not None and self._source_format is not None:
            if format != self._source_format:
                raise ValueError(
                    f"ReportJson and PBIR are not conversible, the report was loaded as `{self._source_format}`, not possible to write as `{format}`"
                )

        fmt = format or self._source_format or ReportFormat.PBIR
        strategy = PbirStrategy() if fmt is ReportFormat.PBIR else ReportJsonStrategy()
        transport = LocalTransport()

        parts = strategy.serialize(self)
        transport.write_parts(parts, root_path)
