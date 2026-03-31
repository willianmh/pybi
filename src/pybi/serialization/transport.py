from typing import Protocol, runtime_checkable

from .types import Part


@runtime_checkable
class TransportWriter(Protocol):
    def write_parts(self, parts: list[Part], root: str) -> None: ...


@runtime_checkable
class TransportReader(Protocol):
    def read_parts(self, root: str) -> list[Part]: ...


class Transport(TransportReader, TransportWriter, Protocol): ...
