import json
from typing import TypeVar

from pydantic import BaseModel

from ...semanticmodel.semanticmodel import SemanticModelDefinition
from ...report.legacy.legacy_model import ReportJsonDefinition
from ...fabric.fabric import DefinitionPbir, DefinitionPbism, Platform
from ..types import Part

StorableModel = (
    DefinitionPbir
    | DefinitionPbism
    | Platform
    | SemanticModelDefinition
    | ReportJsonDefinition
)

T = TypeVar(
    "T",
    DefinitionPbir,
    DefinitionPbism,
    Platform,
    SemanticModelDefinition,
    ReportJsonDefinition,
)


def dump_json_bytes(
    model: BaseModel,
    exclude: set[str] | None = None,
    exclude_none: bool = True,
    exclude_unset: bool = True,
    by_alias: bool = True,
    indent: int = 2,
    encoding: str = "utf-8",
) -> bytes:
    data = model.model_dump(
        mode="json",
        exclude_none=exclude_none,
        exclude_unset=exclude_unset,
        by_alias=by_alias,
        exclude=exclude,
    )
    text = json.dumps(data, indent=indent)
    return text.encode(encoding)


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
