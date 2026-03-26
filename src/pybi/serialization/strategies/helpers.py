import json
from typing import TypeVar

from pydantic import BaseModel

from ...semanticmodel.semanticmodel import SemanticModelDefinition
from ...fabric.fabric import DefinitionPbir, DefinitionPbism, Platform
from ..types import Part

StorableModel = DefinitionPbir | DefinitionPbism | Platform | SemanticModelDefinition

T = TypeVar("T", DefinitionPbir, DefinitionPbism, Platform, SemanticModelDefinition)


def dump_json_bytes(
    model: BaseModel, indent: int = 2, encoding: str = "utf-8"
) -> bytes:
    data = model.model_dump()
    text = json.dumps(data, indent=indent)
    return text.encode(encoding=encoding)


def find_part(parts: list[Part], path: str) -> Part | None:
    for p in parts:
        if p.path == path:
            return p
    return None


def serialize_item(model: StorableModel) -> list[Part]:
    return [Part(path=type(model).FILENAME, payload=dump_json_bytes(model))]


def deserialize_item(parts: list[Part], model_type: type[T]) -> T | None:
    part = find_part(parts, model_type.FILENAME)
    if part:
        return model_type.model_validate(json.loads(part.payload))
    return None
