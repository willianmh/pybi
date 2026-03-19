import json
import logging
from typing import Annotated, Any, TypeVar

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer
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


def str_to_obj(s: str, model: type[T]) -> T:
    return model(**str2dict(s))


def str_to_list_obj(s: str, model: type[T]) -> list[T]:
    return [model(**f) for f in str2dict(s)]


def obj_to_str(obj: T) -> str:
    return json.dumps(
        obj.model_dump(exclude_none=True),
        separators=(",", ":"),
        ensure_ascii=False,
    )


def list_to_str(data: list[T]) -> str:
    return json.dumps(
        [o.model_dump(exclude_none=True) for o in data],
        separators=(",", ":"),
        ensure_ascii=False,
    )


StrListFilter = Annotated[
    list[Filter],
    BeforeValidator(lambda s: str_to_list_obj(s, Filter)),
    PlainSerializer(list_to_str, return_type=str),
]
# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


class Pod(BaseModel):
    model_config = ConfigDict(
        extra="allow",
    )


class ResourcePackage(BaseModel):
    model_config = ConfigDict(
        extra="allow",
    )


class ThemeCollection(BaseModel):
    model_config = ConfigDict(
        extra="allow",
    )


class ModelExtension(BaseModel):
    model_config = ConfigDict(
        extra="allow",
    )


class SlowDataSourceSettings(BaseModel):
    model_config = ConfigDict(
        extra="allow",
    )


# ---------------------------------------------------------------------------
# Main Components
# ---------------------------------------------------------------------------


class Bookmark(BaseModel):
    model_config = ConfigDict(
        extra="allow",
    )


class VisualContainerConfig(BaseModel):
    model_config = ConfigDict(
        extra="allow",
    )


StrVisualContainerConfig = Annotated[
    VisualContainerConfig,
    BeforeValidator(lambda s: str_to_obj(s, VisualContainerConfig)),
    PlainSerializer(obj_to_str, return_type=str),
]


class VisualContainers(BaseModel):
    model_config = ConfigDict(
        extra="allow",
    )
    config: StrVisualContainerConfig


class SectionConfig(BaseModel):
    model_config = ConfigDict(
        extra="allow",
    )


StrSectionConfig = Annotated[
    SectionConfig,
    BeforeValidator(lambda s: str_to_obj(s, SectionConfig)),
    PlainSerializer(obj_to_str, return_type=str),
]


class Section(BaseModel):
    model_config = ConfigDict(
        extra="allow",
    )
    config: StrSectionConfig
    displayName: str = "Page 1"
    displayOption: int = 1
    filters: StrListFilter | None = None
    height: float = 720.00
    name: str = "Section 1"
    ordinal: int | None = None
    visualContainers: list[VisualContainers] = Field(default_factory=list)
    width: float = 1280.00


class ReportConfig(BaseModel):
    model_config = ConfigDict(
        extra="allow",
    )
    version: str | None = None
    themeCollection: ThemeCollection | None = None
    activeSectionIndex: int | None = None
    modelExtensions: list[ModelExtension] | None = None
    bookmarks: list[Bookmark] | None = None
    defaultDrillFilterOtherVisuals: bool | None = None
    filterSortOrder: int | None = None
    slowDataSourceSettings: SlowDataSourceSettings | None = None
    linguisticSchemaSyncVersion: int | None = None
    settings: Any | None = None  # TODO: discover and implement the settings structure
    objects: Any | None = None  # TODO: discover and implement the objects structure


StrReportConfig = Annotated[
    ReportConfig,
    BeforeValidator(lambda s: str_to_obj(s, ReportConfig)),
    PlainSerializer(obj_to_str, return_type=str),
]


class ReportDefinition(BaseModel):
    model_config = ConfigDict(
        extra="allow",
    )
    config: StrReportConfig
    filters: StrListFilter | None = None
    layoutOptimization: int = 0
    pods: list[Pod] | None = None
    publicCustomVisuals: list[str] | None = None
    resourcePackages: list[ResourcePackage] = Field(default_factory=list)
    sections: list[Section] = Field(default_factory=list)
    theme: str | None = None
    name: str | None = None
