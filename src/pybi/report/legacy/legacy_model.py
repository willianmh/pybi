import json
import logging
from typing import Annotated, Any, ClassVar, TypeVar

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer
from pydantic.functional_validators import BeforeValidator


from ..pbir.models.semanticquery.expressions import (
    EntitySource,
    ParsedExpressionContainer,
    QueryExpressionContainer,
    QuerySortClause,
)
from ...expressions.filter import Filter

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


def obj_to_str(obj: BaseModel) -> str:
    return json.dumps(
        obj.model_dump(exclude_none=True),
        separators=(",", ":"),
        ensure_ascii=False,
    )


def list_to_str(data: list[BaseModel]) -> str:
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


class PodConfig(BaseModel):
    model_config = ConfigDict(extra="allow")


class Parameter(BaseModel):
    model_config = ConfigDict(extra="allow")


StrPodConfig = Annotated[
    PodConfig,
    BeforeValidator(lambda s: str_to_obj(s, PodConfig)),
    PlainSerializer(obj_to_str, return_type=str),
]

StrListParameter = Annotated[
    list[Parameter],
    BeforeValidator(lambda s: str_to_list_obj(s, Parameter)),
    PlainSerializer(list_to_str, return_type=str),
]


class Pod(BaseModel):
    model_config = ConfigDict(extra="allow")

    boundSection: str
    config: StrPodConfig
    name: str
    parameters: StrListParameter | None = None
    referenceScope: int | None = None
    type: int | None = None


default_resource_package = {
    "disabled": False,
    "items": [{"name": "CY24SU10", "path": "BaseThemes/CY24SU10.json", "type": 202}],
    "name": "SharedResources",
    "type": 2,
}


class ResourcePackage(BaseModel):
    model_config = ConfigDict(extra="allow")
    resourcePackage: dict[str, Any] = Field(
        default_factory=lambda: default_resource_package.copy()
    )


class ThemeCollection(BaseModel):
    model_config = ConfigDict(extra="allow")


class ModelExtension(BaseModel):
    model_config = ConfigDict(extra="allow")


class SlowDataSourceSettings(BaseModel):
    model_config = ConfigDict(extra="allow")


# ---------------------------------------------------------------------------
# Visual Container
# ---------------------------------------------------------------------------


class Position(BaseModel):
    model_config = ConfigDict(extra="allow")


class Layout(BaseModel):
    id: int
    position: Position


class PrototypeQuery(BaseModel):
    model_config = ConfigDict(extra="allow")

    Version: int | None = None
    From: list[EntitySource] | None = None
    Select: list[ParsedExpressionContainer] | None = None
    OrderBy: list[QuerySortClause] | None = None


class Level(BaseModel):
    model_config = ConfigDict(extra="allow")

    queryRefs: list[str]
    isCollapsed: bool | None = None
    identityKeys: list[QueryExpressionContainer] | None = None
    isPinned: bool | None = None


class ExpansionState(BaseModel):
    model_config = ConfigDict(extra="allow")

    roles: list[str]
    levels: list[Level]
    root: dict


class QueryOptions(BaseModel):
    model_config = ConfigDict(extra="allow")

    keepProjectionOrder: bool
    allowBinnedLineSample: bool | None = None


class Display(BaseModel):
    model_config = ConfigDict(extra="allow")

    mode: str


class SyncGroup(BaseModel):
    model_config = ConfigDict(extra="allow")

    groupName: str
    fieldChanges: bool
    filterChanges: bool


class SingleVisualGroup(BaseModel):
    displayName: str
    groupMode: int
    isHidden: bool | None = None
    objects: dict | None = None  # TODO: discover and implement


class SingleVisual(BaseModel):
    model_config = ConfigDict(extra="allow")
    visualType: str | None = None
    projections: dict | None = None  # TODO: discover and implement
    prototypeQuery: PrototypeQuery | None = None
    expansionStates: list[ExpansionState] | None = None
    queryFieldParametersByRole: dict | None = None  # TODO: discover and implement
    columnProperties: dict | None = None  # TODO: discover and implement
    queryOptions: QueryOptions | None = None
    display: Display | None = None
    showAllRoles: list[str] | None = None
    syncGroup: SyncGroup | None = None
    drillFilterOtherVisuals: bool | None = None
    filterSortOrder: int | None = None
    hasDefaultSort: bool | None = None
    objects: dict | None = None  # TODO implement objects Model
    vcObjects: dict | None = None  # TODO implement vcObjects Model
    cachedFilterDisplayItems: list | None = None
    filterExpressionMetadata: dict[str, Any] | None = (
        None  # TODO: discover and implement
    )
    title: dict | None = None  # TODO implement title Model
    border: dict | None = None  # TODO implement border Model


# ---------------------------------------------------------------------------
# Main Components
# ---------------------------------------------------------------------------


class Bookmark(BaseModel):
    model_config = ConfigDict(extra="allow")


class VisualContainerConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    layouts: list[Layout] | None = None
    singleVisual: SingleVisual | None = None
    singleVisualGroup: SingleVisualGroup | None = None
    parentGroupName: str | None = None
    howCreated: str | None = None


StrVisualContainerConfig = Annotated[
    VisualContainerConfig,
    BeforeValidator(lambda s: str_to_obj(s, VisualContainerConfig)),
    PlainSerializer(obj_to_str, return_type=str),
]


class VisualContainer(BaseModel):
    model_config = ConfigDict(extra="allow")

    config: StrVisualContainerConfig
    filters: StrListFilter | None = None
    height: float
    width: float
    x: float
    y: float
    z: float


class SectionConfig(BaseModel):
    model_config = ConfigDict(extra="allow")


StrSectionConfig = Annotated[
    SectionConfig,
    BeforeValidator(lambda s: str_to_obj(s, SectionConfig)),
    PlainSerializer(obj_to_str, return_type=str),
]


class Section(BaseModel):
    model_config = ConfigDict(extra="allow")

    config: StrSectionConfig
    displayName: str = "Page 1"
    displayOption: int = 1
    filters: StrListFilter | None = None
    height: float = 720.00
    name: str = "Section 1"
    ordinal: int | None = None
    visualContainers: list[VisualContainer] = Field(default_factory=list)
    width: float = 1280.00


class ReportConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

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


class ReportJsonDefinition(BaseModel):
    _FILENAME: ClassVar[str] = "report.json"
    model_config = ConfigDict(extra="allow")

    config: StrReportConfig
    filters: StrListFilter | None = None
    layoutOptimization: int = 0
    pods: list[Pod] | None = None
    publicCustomVisuals: list[str] | None = None
    resourcePackages: list[ResourcePackage] = Field(default_factory=list)
    sections: list[Section] = Field(default_factory=list)
    theme: str | None = None
    name: str | None = None
