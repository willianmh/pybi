from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, PrivateAttr

from ..fabric.fabric import DefinitionPbism, Platform
from .definition import Column, Expression, Measure, Model, Relationship, Role, Table, SemanticModelDefinition
from .types import SemanticModelFormat

if TYPE_CHECKING:
    from ..collections import NamedList


class SemanticModel(BaseModel):
    item_definition: DefinitionPbism
    definition: SemanticModelDefinition
    platform: Platform

    _ROOT_PATH: str | None = PrivateAttr(default="MyPowerBIDashboard.SemanticModel")

    _source_format: SemanticModelFormat | None = PrivateAttr(default=None)

    # ── convenience read properties ───────────────────────────────────────────

    @property
    def tables(self) -> "NamedList[Table]":
        """All tables in the model.  Supports name-based indexing:
        ``sm.tables["Sales"]``.  Returns an empty :class:`~pybi.collections.NamedList`
        when the model has no tables.
        """
        from ..collections import NamedList as NL
        return self.definition.model.tables or NL()  # type: ignore[return-value]

    @property
    def relationships(self) -> list[Relationship]:
        """All relationships in the model."""
        return self.definition.model.relationships or []

    @property
    def roles(self) -> "NamedList[Role]":
        """All roles in the model.  Supports name-based indexing."""
        from ..collections import NamedList as NL
        return self.definition.model.roles or NL()  # type: ignore[return-value]

    @property
    def expressions(self) -> "NamedList[Expression]":
        """All shared expressions (M parameters / functions).  Supports
        name-based indexing."""
        from ..collections import NamedList as NL
        return self.definition.model.expressions or NL()  # type: ignore[return-value]

    @property
    def measures(self) -> list[tuple[Table, Measure]]:
        """All measures across all tables as ``(table, measure)`` pairs.

        Use :meth:`get_measure` for a direct name lookup, or access a specific
        table first — ``sm.tables["Sales"].measures["Total Revenue"]`` — for
        unambiguous table-scoped access.
        """
        result: list[tuple[Table, Measure]] = []
        for t in self.tables:
            for m in (t.measures or []):
                result.append((t, m))
        return result

    @property
    def columns(self) -> list[tuple[Table, Column]]:
        """All columns across all tables as ``(table, column)`` pairs."""
        result: list[tuple[Table, Column]] = []
        for t in self.tables:
            for c in (t.columns or []):
                result.append((t, c))
        return result

    # ── lookup helpers ────────────────────────────────────────────────────────

    def get_table(self, name: str) -> Table:
        """Return the table named *name*.

        Raises :class:`~pybi.errors.TableNotFoundError` if not found.
        """
        return self.definition.model.get_table(name)

    def find_table(self, name: str) -> Table | None:
        """Return the table named *name*, or ``None`` if not found."""
        return self.definition.model.find_table(name)

    def get_measure(self, name: str, *, table: str | None = None) -> Measure:
        """Return a measure by name, optionally scoped to a single table.

        Raises :class:`~pybi.errors.MeasureNotFoundError` if the measure cannot
        be found (or is ambiguous without a *table* scope).
        """
        from ..errors import MeasureNotFoundError
        for t in self.tables:
            if table is not None and t.name != table:
                continue
            m = t.find_measure(name)
            if m is not None:
                return m
        raise MeasureNotFoundError(name, table=table)

    def find_measure(self, name: str, *, table: str | None = None) -> Measure | None:
        """Return a measure by name, or ``None`` if not found."""
        for t in self.tables:
            if table is not None and t.name != table:
                continue
            m = t.find_measure(name)
            if m is not None:
                return m
        return None

    def get_column(self, table: str, name: str) -> Column:
        """Return the column named *name* in *table*.

        Raises :class:`~pybi.errors.ColumnNotFoundError` if not found.
        """
        return self.get_table(table).get_column(name)

    def find_column(self, table: str, name: str) -> Column | None:
        """Return the column named *name* in *table*, or ``None`` if not found."""
        t = self.find_table(table)
        return t.find_column(name) if t else None

    # ── mutation helpers ──────────────────────────────────────────────────────

    def add_table(self, table: Table) -> None:
        """Add *table* to the model, raising
        :class:`~pybi.errors.DuplicateNameError` if a table with the same name
        already exists.
        """
        self.definition.model.add_table(table)

    def remove_table(self, name: str) -> Table:
        """Remove and return the table named *name*.

        Raises :class:`~pybi.errors.TableNotFoundError` if not found.
        """
        return self.definition.model.remove_table(name)

    # ── persistence ───────────────────────────────────────────────────────────

    def save(self, format: SemanticModelFormat | None = None) -> None:
        """Write back to the path this model was read from.

        Equivalent to ``sm.write(original_path, format)``.  Raises
        ``ValueError`` when the model was not loaded from a path (e.g. it was
        constructed programmatically without specifying ``root_path``).
        """
        self.write(self._ROOT_PATH, format)

    @classmethod
    def read(cls, root_path: str | Path) -> SemanticModel:
        from ..serialization.strategies import TmdlStrategy, ModelBimStrategy
        from ..serialization.transport import LocalTransport
        from ..serialization.detect import detect_semantic_model_format

        fmt = detect_semantic_model_format(root_path=root_path)
        strategy = (
            TmdlStrategy() if fmt is SemanticModelFormat.TMDL else ModelBimStrategy()
        )
        transport = LocalTransport()

        parts = transport.read_parts(root_path)
        sm = strategy.deserialize(parts=parts)
        sm._ROOT_PATH = str(root_path)
        sm._source_format = fmt
        return sm

    def write(
        self,
        root_path: str | Path | None,
        format: SemanticModelFormat | None = None,
    ):
        from ..serialization.strategies import TmdlStrategy, ModelBimStrategy
        from ..serialization.transport import LocalTransport

        root_path = root_path or self._ROOT_PATH
        if not root_path:
            raise ValueError("You must provide a root_path.")

        fmt = format or self._source_format or SemanticModelFormat.TMDL
        strategy = (
            TmdlStrategy() if fmt is SemanticModelFormat.TMDL else ModelBimStrategy()
        )
        transport = LocalTransport()

        parts = strategy.serialize(self)
        transport.write_parts(parts, root_path)
