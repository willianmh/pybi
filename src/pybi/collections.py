"""Typed list with name-based indexing and duplicate-name validation.

``NamedList[T]`` is a plain ``list`` subclass, so it passes ``isinstance(x, list)``
checks and is accepted by Pydantic fields typed as ``list[T]``.  It adds three
capabilities on top of a regular list:

1. **String indexing** - ``collection["Sales"]`` finds the item whose ``name``
   attribute equals ``"Sales"``, raising ``KeyError`` if absent.
2. **Membership test by name** - ``"Sales" in collection`` returns ``True`` when
   any item has that name.
3. **Duplicate-name guard on ``append`` / ``insert``** - trying to add an item
   whose name already exists raises :class:`~pybi.errors.DuplicateNameError`.
   The guard is intentionally *not* applied in ``__init__`` so that data loaded
   from existing files (which may pre-date validation) is never rejected.

Direct list operations (``collection[0]``, iteration, ``len()``, slicing) all
work exactly as on a regular ``list``.

Mutating the underlying list via inherited methods other than ``append`` and
``insert`` (e.g. ``list.extend``, ``list.__setitem__``) bypasses the duplicate
guard and is an intentional power-user escape hatch.
"""

from __future__ import annotations

from typing import Generic, Iterator, TypeVar, overload

T = TypeVar("T")


class NamedList(list, Generic[T]):
    """A ``list`` subclass that also supports name-based indexing and validates
    uniqueness when items are appended or inserted.

    Items are expected to have a ``name`` attribute (``str | None``).  Items
    whose ``name`` is ``None`` are stored normally but are invisible to
    string-key lookups.

    Examples
    --------
    >>> measures = NamedList([Measure(name="Revenue", expression="SUM(...)")])
    >>> measures["Revenue"]          # O(n) lookup by name
    Measure(name='Revenue', ...)
    >>> measures.get("Missing")      # None if not found
    None
    >>> "Revenue" in measures        # membership by name
    True
    >>> measures.append(Measure(name="Revenue", ...))  # raises DuplicateNameError
    """

    # - initialisation ----------------------------

    def __init__(self, items: list[T] | None = None) -> None:
        super().__init__(items or [])

    # - item access -----------------------------─

    @overload
    def __getitem__(self, key: int) -> T: ...
    @overload
    def __getitem__(self, key: str) -> T: ...
    @overload
    def __getitem__(self, key: slice) -> list[T]: ...

    def __getitem__(self, key):  # type: ignore[override]
        if isinstance(key, str):
            for item in self:
                if getattr(item, "name", None) == key:
                    return item
            raise KeyError(key)
        return super().__getitem__(key)

    # - membership ------------------------------

    def __contains__(self, item: object) -> bool:  # type: ignore[override]
        if isinstance(item, str):
            return any(getattr(x, "name", None) == item for x in self)
        return super().__contains__(item)

    # - convenience helpers -------------------------─

    def get(self, name: str, default: T | None = None) -> T | None:
        """Return the item with the given name, or *default* if not present."""
        for item in self:
            if getattr(item, "name", None) == name:
                return item
        return default

    def names(self) -> list[str]:
        """Return a list of all item names (skipping items with ``name=None``)."""
        return [n for item in self if (n := getattr(item, "name", None)) is not None]

    # - mutation with validation -----------------------

    def _check_duplicate(self, item: T) -> None:
        name = getattr(item, "name", None)
        if name is not None and name in self:
            from pybi.errors import DuplicateNameError

            raise DuplicateNameError(name)

    def append(self, item: T) -> None:
        """Append *item*, raising :class:`~pybi.errors.DuplicateNameError` if
        an item with the same name already exists."""
        self._check_duplicate(item)
        super().append(item)

    def insert(self, index: int, item: T) -> None:  # type: ignore[override]
        """Insert *item* at *index*, raising :class:`~pybi.errors.DuplicateNameError`
        if an item with the same name already exists."""
        self._check_duplicate(item)
        super().insert(index, item)

    # - dunder helpers ----------------------------

    def __repr__(self) -> str:
        return f"NamedList({list.__repr__(self)})"

    def __iter__(self) -> Iterator[T]:  # type: ignore[override]
        return super().__iter__()  # type: ignore[return-value]
