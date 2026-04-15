from pathlib import Path

from pydantic import BaseModel, PrivateAttr

from ..fabric.fabric import DefinitionPbir, Platform
from .adapters import make_report_view
from .definition import ReportDefinition, Bookmark, Page, Visual
from .legacy.legacy_model import ReportJsonDefinition
from .pbir.definition import PbirReportDefinition
from .types import ReportFormat


class Report(BaseModel):
    item_definition: DefinitionPbir
    raw_definition: ReportJsonDefinition | PbirReportDefinition
    platform: Platform

    _ROOT_PATH: str | None = PrivateAttr(default="MyPowerBIDashboard.Report")
    _source_format: ReportFormat | None = PrivateAttr(default=None)
    _view: ReportDefinition | None = PrivateAttr(default=None)

    # - convenience read properties ---------------------─

    @property
    def definition(self) -> ReportDefinition:
        """Format-agnostic view of the report definition."""
        if self._view is None:
            self._view = make_report_view(self.raw_definition)
        return self._view

    @property
    def pages(self) -> list[Page]:
        """All pages in the report. Works for both PBIR and legacy formats."""
        return list(self.definition.pages)

    def get_page(self, display_name: str) -> Page:
        """Return the page whose display name equals *display_name*.

        Raises :class:`~pybi.errors.PageNotFoundError` if no matching page is
        found. Works for both PBIR and legacy formats.
        """
        for p in self.definition.pages:
            if p.display_name == display_name:
                return p
        from ..errors import PageNotFoundError

        raise PageNotFoundError(display_name)

    def find_page(self, display_name: str) -> Page | None:
        """Return the page whose display name equals *display_name*, or
        ``None`` if not found."""
        for p in self.definition.pages:
            if p.display_name == display_name:
                return p
        return None

    @property
    def visuals(self) -> list[Visual]:
        """All visuals across all pages, in page order."""
        return [v for p in self.pages for v in p.visuals]

    @property
    def bookmarks(self) -> list[Bookmark]:
        """All bookmarks defined in the report. Works for both PBIR and legacy formats."""
        return list(self.definition.bookmarks)

    # - persistence -----------------------------─

    def save(self, format: ReportFormat | None = None) -> None:
        """Write back to the path this report was read from.

        Equivalent to ``report.write(original_path, format)``.  Raises
        ``ValueError`` when the report was not loaded from a path.
        """
        self.write(self._ROOT_PATH, format)

    @classmethod
    def read(cls, root_path: str | Path) -> Report:
        from ..serialization.detect import detect_report_format
        from ..serialization.strategies import PbirStrategy, ReportJsonStrategy
        from ..serialization.transport import LocalTransport

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
