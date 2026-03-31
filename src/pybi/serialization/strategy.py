from typing import Protocol, TypeVar, runtime_checkable

from .types import Part

T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)
T_contra = TypeVar("T_contra", contravariant=True)


@runtime_checkable
class SerializationStrategy(Protocol[T_contra]):
    def serialize(self, model: T_contra) -> list[Part]: ...


@runtime_checkable
class DeserializationStrategy(Protocol[T_co]):
    def deserialize(self, parts: list[Part]) -> T_co: ...


@runtime_checkable
class IOStrategy(SerializationStrategy[T], DeserializationStrategy[T], Protocol[T]): ...
