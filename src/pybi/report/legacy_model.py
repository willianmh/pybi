import json
import logging
from typing import Annotated, TypeVar

from pydantic import BaseModel, Field, PlainSerializer
from pydantic.functional_validators import BeforeValidator

from ..expressions.filter import Filter

logger = logging.getLogger(__name__)


def str2dict(data: str) -> dict:
    if not isinstance(data, str):
        raise TypeError(f"Expected str, got {type(data).__name__}")
    try:
        return json.loads(data)
    except Exception as e:
        raise e


T = TypeVar("T", bound=BaseModel)


def str_to_list_obj(s: str, model: type[T]) -> list[T]:
    return [model(**f) for f in str2dict(s)]


def list_to_str(data: list[T]) -> str:
    return json.dumps(
        [o.model_dump(exclude_none=True) for o in data],
        separators=(",", ":"),
        ensure_ascii=False,
    )


StrFilter = Annotated[
    list[Filter],
    BeforeValidator(lambda s: str_to_list_obj(s, Filter)),
    PlainSerializer(list_to_str, return_type=str),
]


class Config(BaseModel): ...


class Pod(BaseModel): ...


class ResourcePackage(BaseModel): ...


class Section(BaseModel): ...


class ReportDefinition(BaseModel):
    config: Config
    filters: StrFilter | None = None
    layoutOptimization: int = 0
    pods: list[Pod] | None = None
    publicCustomVisuals: list[str] | None = None
    resourcePackages: list[ResourcePackage] = Field(default_factory=list)
    sections: list[Section] = Field(default_factory=list)
    theme: str | None = None
    name: str | None
