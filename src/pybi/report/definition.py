from typing import Any, Protocol, Sequence, runtime_checkable


@runtime_checkable
class Filter(Protocol):
    @property
    def name(self) -> str | None: ...

    @property
    def display_name(self) -> str | None: ...

    @property
    def type(self) -> str | None: ...

    @property
    def is_hidden_in_view_mode(self) -> bool | None: ...

    @property
    def is_locked_in_view_mode(self) -> bool | None: ...

    @property
    def raw(self) -> Any: ...


@runtime_checkable
class Visual(Protocol):
    @property
    def name(self) -> str | None: ...

    @property
    def visual_type(self) -> str | None: ...

    @property
    def x(self) -> float: ...

    @property
    def y(self) -> float: ...

    @property
    def z(self) -> float | None: ...

    @property
    def width(self) -> float: ...

    @property
    def height(self) -> float: ...

    @property
    def filters(self) -> Sequence[Filter]: ...

    @property
    def raw(self) -> Any: ...


@runtime_checkable
class Page(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def display_name(self) -> str: ...

    @property
    def width(self) -> float | None: ...

    @property
    def height(self) -> float | None: ...

    @property
    def visuals(self) -> Sequence[Visual]: ...

    @property
    def filters(self) -> Sequence[Filter]: ...

    @property
    def raw(self) -> Any: ...


@runtime_checkable
class Bookmark(Protocol):
    @property
    def name(self) -> str | None: ...

    @property
    def display_name(self) -> str | None: ...

    @property
    def raw(self) -> Any: ...


@runtime_checkable
class ReportDefinition(Protocol):
    @property
    def pages(self) -> Sequence[Page]: ...

    @property
    def bookmarks(self) -> Sequence[Bookmark]: ...
