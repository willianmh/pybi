"""Serialization and deserialization utilities for pybi models."""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def serialize(model: BaseModel, *, exclude_none: bool = True) -> str:
    """Serialize a Pydantic model to a JSON string.

    Args:
        model: The Pydantic model instance to serialize.
        exclude_none: If True, omit fields with ``None`` values (default: True).

    Returns:
        A JSON string representation of the model.
    """
    return model.model_dump_json(exclude_none=exclude_none)


def deserialize(cls: type[T], data: str | bytes) -> T:
    """Deserialize JSON data into a Pydantic model instance.

    Args:
        cls: The target Pydantic model class.
        data: The JSON string or bytes to deserialize.

    Returns:
        An instance of the target model class.
    """
    return cls.model_validate_json(data)
