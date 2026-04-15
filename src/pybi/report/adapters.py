"""Format adapters: wrap legacy and PBIR internal models behind the public view Protocols.

This module contains the only ``isinstance`` dispatch in the report public API.
All other code works exclusively through the Protocol types defined in
``pybi.report.definition``.
"""

from typing import Any

from ..expressions.filter import Filter as LegacyFilter
from .definition import Bookmark, Filter, Page, ReportDefinition, Visual
from .legacy.legacy_model import (
    Bookmark as LegacyBookmark,
)
from .legacy.legacy_model import (
    ReportJsonDefinition,
    Section,
)
from .legacy.legacy_model import (
    VisualContainer as LegacyVisualContainerModel,
)
from .pbir.definition import PbirReportDefinition
from .pbir.types import AnyBookmark, AnyVisualContainer, PbirPageWithVisuals

# ---------------------------------------------------------------------------
# Filter adapters
# ---------------------------------------------------------------------------


class LegacyFilterView:
    """Adapts a legacy :class:`~pybi.expressions.filter.Filter` to :class:`Filter`."""

    def __init__(self, f: LegacyFilter) -> None:
        self._f = f

    @property
    def name(self) -> str | None:
        return self._f.name

    @property
    def display_name(self) -> str | None:
        return self._f.displayName

    @property
    def type(self) -> str | None:
        return self._f.type.value if self._f.type is not None else None

    @property
    def is_hidden_in_view_mode(self) -> bool | None:
        return self._f.isHiddenInViewMode

    @property
    def is_locked_in_view_mode(self) -> bool | None:
        return self._f.isLockedInViewMode

    @property
    def raw(self) -> Any:
        return self._f


class PbirFilterView:
    """Adapts a PBIR ``FilterContainer`` (any version) to :class:`Filter`.

    The ``FilterContainer`` type is defined inline inside each versioned page/visual
    model's embedded schema.  We accept ``Any`` here and access fields by name.
    """

    def __init__(self, fc: Any) -> None:
        self._fc = fc

    @property
    def name(self) -> str | None:
        return getattr(self._fc, "name", None)

    @property
    def display_name(self) -> str | None:
        return getattr(self._fc, "displayName", None)

    @property
    def type(self) -> str | None:
        t = getattr(self._fc, "type", None)
        return t.value if t is not None else None

    @property
    def is_hidden_in_view_mode(self) -> bool | None:
        return getattr(self._fc, "isHiddenInViewMode", None)

    @property
    def is_locked_in_view_mode(self) -> bool | None:
        return getattr(self._fc, "isLockedInViewMode", None)

    @property
    def raw(self) -> Any:
        return self._fc


# ---------------------------------------------------------------------------
# Visual adapters
# ---------------------------------------------------------------------------


class LegacyVisualView:
    """Adapts a legacy :class:`~pybi.report.legacy.legacy_model.VisualContainer`
    to :class:`VisualView`."""

    def __init__(self, vc: LegacyVisualContainerModel) -> None:
        self._vc = vc

    @property
    def name(self) -> str | None:
        return self._vc.config.name

    @property
    def visual_type(self) -> str | None:
        sv = self._vc.config.singleVisual
        return sv.visualType if sv is not None else None

    @property
    def x(self) -> float:
        return self._vc.x

    @property
    def y(self) -> float:
        return self._vc.y

    @property
    def z(self) -> float | None:
        return self._vc.z

    @property
    def width(self) -> float:
        return self._vc.width

    @property
    def height(self) -> float:
        return self._vc.height

    @property
    def filters(self) -> list[Filter]:
        return [LegacyFilterView(f) for f in (self._vc.filters or [])]

    @property
    def raw(self) -> Any:
        return self._vc


class PbirVisualView:
    """Adapts any versioned PBIR ``VisualContainer`` to :class:`VisualView`.

    Uses ``getattr`` throughout to handle both strict versioned models and the
    permissive ``PbirVisualContainer`` fallback.
    """

    def __init__(self, vc: AnyVisualContainer) -> None:
        self._vc = vc

    @property
    def name(self) -> str | None:
        return getattr(self._vc, "name", None)

    @property
    def visual_type(self) -> str | None:
        visual = getattr(self._vc, "visual", None)
        return getattr(visual, "visualType", None)

    @property
    def x(self) -> float:
        pos = getattr(self._vc, "position", None)
        return getattr(pos, "x", 0.0)

    @property
    def y(self) -> float:
        pos = getattr(self._vc, "position", None)
        return getattr(pos, "y", 0.0)

    @property
    def z(self) -> float | None:
        pos = getattr(self._vc, "position", None)
        return getattr(pos, "z", None)

    @property
    def width(self) -> float:
        pos = getattr(self._vc, "position", None)
        return getattr(pos, "width", 0.0)

    @property
    def height(self) -> float:
        pos = getattr(self._vc, "position", None)
        return getattr(pos, "height", 0.0)

    @property
    def filters(self) -> list[Filter]:
        fc = getattr(self._vc, "filterConfig", None)
        raw_filters = (
            (fc.filters or []) if fc is not None and hasattr(fc, "filters") else []
        )
        return [PbirFilterView(f) for f in raw_filters]

    @property
    def raw(self) -> Any:
        return self._vc


# ---------------------------------------------------------------------------
# Page adapters
# ---------------------------------------------------------------------------


class LegacyPageView:
    """Adapts a legacy :class:`~pybi.report.legacy.legacy_model.Section`
    to :class:`PageView`."""

    def __init__(self, section: Section) -> None:
        self._section = section

    @property
    def name(self) -> str:
        return self._section.name

    @property
    def display_name(self) -> str:
        return self._section.displayName

    @property
    def width(self) -> float | None:
        return self._section.width

    @property
    def height(self) -> float | None:
        return self._section.height

    @property
    def visuals(self) -> list[Visual]:
        return [LegacyVisualView(v) for v in self._section.visualContainers]

    @property
    def filters(self) -> list[Filter]:
        return [LegacyFilterView(f) for f in (self._section.filters or [])]

    @property
    def raw(self) -> Any:
        return self._section


class PbirPageView:
    """Adapts a :class:`~pybi.report.pbir.types.PbirPageWithVisuals` to
    :class:`PageView`.

    Uses ``getattr`` to handle both strict versioned ``Page`` models and the
    permissive ``PbirPage`` fallback.
    """

    def __init__(self, pwv: PbirPageWithVisuals) -> None:
        self._pwv = pwv

    @property
    def name(self) -> str:
        return getattr(self._pwv.page, "name", "")

    @property
    def display_name(self) -> str:
        return getattr(self._pwv.page, "displayName", "")

    @property
    def width(self) -> float | None:
        return getattr(self._pwv.page, "width", None)

    @property
    def height(self) -> float | None:
        return getattr(self._pwv.page, "height", None)

    @property
    def visuals(self) -> list[Visual]:
        return [PbirVisualView(v) for v in self._pwv.visuals]

    @property
    def filters(self) -> list[Filter]:
        fc = getattr(self._pwv.page, "filterConfig", None)
        raw_filters = (
            (fc.filters or []) if fc is not None and hasattr(fc, "filters") else []
        )
        return [PbirFilterView(f) for f in raw_filters]

    @property
    def raw(self) -> Any:
        return self._pwv


# ---------------------------------------------------------------------------
# Bookmark adapters
# ---------------------------------------------------------------------------


class LegacyBookmarkView:
    """Adapts a legacy :class:`~pybi.report.legacy.legacy_model.Bookmark`
    (``extra="allow"``) to :class:`BookmarkView`."""

    def __init__(self, bm: LegacyBookmark) -> None:
        self._bm = bm

    @property
    def name(self) -> str | None:
        return getattr(self._bm, "name", None)

    @property
    def display_name(self) -> str | None:
        return getattr(self._bm, "displayName", None)

    @property
    def raw(self) -> Any:
        return self._bm


class PbirBookmarkView:
    """Adapts any versioned PBIR bookmark to :class:`BookmarkView`."""

    def __init__(self, bm: AnyBookmark) -> None:
        self._bm = bm

    @property
    def name(self) -> str | None:
        return getattr(self._bm, "name", None)

    @property
    def display_name(self) -> str | None:
        return getattr(self._bm, "displayName", None)

    @property
    def raw(self) -> Any:
        return self._bm


# ---------------------------------------------------------------------------
# Report view helpers (private)
# ---------------------------------------------------------------------------


class _LegacyReportView:
    def __init__(self, definition: ReportJsonDefinition) -> None:
        self._definition = definition

    @property
    def pages(self) -> list[Page]:
        return [LegacyPageView(s) for s in self._definition.sections]

    @property
    def bookmarks(self) -> list[Bookmark]:
        return [
            LegacyBookmarkView(b) for b in (self._definition.config.bookmarks or [])
        ]


class _PbirReportView:
    def __init__(self, definition: PbirReportDefinition) -> None:
        self._definition = definition

    @property
    def pages(self) -> list[Page]:
        return [PbirPageView(p) for p in self._definition.pages]

    @property
    def bookmarks(self) -> list[Bookmark]:
        return [PbirBookmarkView(b) for b in self._definition.bookmarks]


# ---------------------------------------------------------------------------
# Factory — the only isinstance dispatch in the public report API
# ---------------------------------------------------------------------------


def make_report_view(
    definition: ReportJsonDefinition | PbirReportDefinition,
) -> ReportDefinition:
    """Return the appropriate :class:`ReportView` for *definition*.

    This is the single ``isinstance`` dispatch point in the report public API.
    All other report code works through the Protocol interfaces.
    """
    if isinstance(definition, PbirReportDefinition):
        return _PbirReportView(definition)
    return _LegacyReportView(definition)
