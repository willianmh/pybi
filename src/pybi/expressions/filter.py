from enum import Enum

from pydantic import BaseModel, ConfigDict

from ..report.models.semanticquery.expressions import (
    FilterDefinition,
    QueryExpressionContainer,
)


class FilterTypeEnum(Enum):
    CATEGORICAL = "Categorical"
    ADVANCED = "Advanced"
    TOPN = "TopN"
    RELATIVE_DATE = "RelativeDate"


class FilterObjectProperty(BaseModel):
    expr: QueryExpressionContainer


class FilterObjectProperties(BaseModel):
    isInvertedSelectionMode: FilterObjectProperty | None = None
    requireSingleSelect: FilterObjectProperty | None = None


class FilterObjectEntry(BaseModel):
    properties: FilterObjectProperties


class FilterObjects(BaseModel):
    general: list[FilterObjectEntry] | None = None


class Filter(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    name: str | None = None
    expression: QueryExpressionContainer | None = None
    filter: FilterDefinition | None = None
    type: FilterTypeEnum = FilterTypeEnum("Categorical")
    cachedDisplayNames: list | None = None  # Todo: list of what?
    howCreated: int | None = None
    objects: FilterObjects | None = None  # Todo: Any?
    isHiddenInViewMode: bool | None = None
    isLockedInViewMode: bool | None = None
    displayName: str | None = None
    ordinal: int | None = None
