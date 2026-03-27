import json
from typing import TypeVar, overload

from pydantic import BaseModel

from ...fabric.fabric import DefinitionPbir, DefinitionPbism, PBIProject, Platform
from ...report.legacy.legacy_model import ReportJsonDefinition
from ...semanticmodel.semanticmodel import SemanticModelDefinition
from ..types import Part

StorableModel = (
    DefinitionPbir
    | DefinitionPbism
    | Platform
    | SemanticModelDefinition
    | ReportJsonDefinition
    | PBIProject
)

T = TypeVar(
    "T",
    DefinitionPbir,
    DefinitionPbism,
    Platform,
    SemanticModelDefinition,
    ReportJsonDefinition,
    PBIProject,
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


@overload
def to_part(model: StorableModel) -> Part: ...
@overload
def to_part(model: BaseModel, path: str) -> Part: ...
def to_part(model, path=None):
    return Part(
        path=path if path is not None else type(model)._FILENAME,
        payload=dump_json_bytes(model),
    )


@overload
def from_parts(parts: list[Part], model_type: type[T]) -> T | None: ...
@overload
def from_parts(
    parts: list[Part], model_type: type[BaseModel], path: str
) -> BaseModel | None: ...
def from_parts(parts, model_type, path=None):
    target = path if path is not None else model_type._FILENAME
    part = find_part(parts, target)
    return model_type.model_validate(json.loads(part.payload)) if part else None
