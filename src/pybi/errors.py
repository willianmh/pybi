"""Structured error taxonomy for pybi.

All public exceptions raised by the library are subclasses of :class:`PyBIError`,
making it easy to catch any pybi-specific error with a single ``except`` clause.
"""

from __future__ import annotations


class PyBIError(Exception):
    """Base class for all pybi exceptions."""


# ── I/O errors ────────────────────────────────────────────────────────────────


class ArtifactNotFoundError(PyBIError):
    """Raised when a Power BI artifact file or folder cannot be found."""


class UnsupportedFormatError(PyBIError):
    """Raised when a file format is not recognized or not supported."""


# ── Semantic model lookup errors ──────────────────────────────────────────────


class TableNotFoundError(PyBIError):
    """Raised when a named table does not exist in the semantic model."""

    def __init__(self, name: str) -> None:
        super().__init__(f"Table {name!r} not found in semantic model")
        self.name = name


class MeasureNotFoundError(PyBIError):
    """Raised when a named measure cannot be found."""

    def __init__(self, name: str, *, table: str | None = None) -> None:
        scope = f" in table {table!r}" if table else " in semantic model"
        super().__init__(f"Measure {name!r} not found{scope}")
        self.name = name
        self.table = table


class ColumnNotFoundError(PyBIError):
    """Raised when a named column cannot be found."""

    def __init__(self, name: str, *, table: str | None = None) -> None:
        scope = f" in table {table!r}" if table else " in semantic model"
        super().__init__(f"Column {name!r} not found{scope}")
        self.name = name
        self.table = table


class DuplicateNameError(PyBIError):
    """Raised when adding an item whose name already exists in the collection."""

    def __init__(self, name: str) -> None:
        super().__init__(f"An item named {name!r} already exists in this collection")
        self.name = name


# ── Report lookup errors ───────────────────────────────────────────────────────


class PageNotFoundError(PyBIError):
    """Raised when a named report page cannot be found."""

    def __init__(self, name: str) -> None:
        super().__init__(f"Report page {name!r} not found")
        self.name = name
