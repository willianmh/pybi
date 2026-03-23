import uuid
from typing import Any

from pydantic import BaseModel, Field

from ..fabric.fabric import DefinitionPbism, Platform
from .types import ColumnType, DataCategory, DataType, PartitionMode, SourceType


class Culture(BaseModel):
    name: str = "en-US"
    linguisticMetadata: dict[str, Any] = {
        "content": {"Language": "en-US", "Version": "1.0.0"},
        "contentType": "json",
    }


class Source(BaseModel):
    entityName: str | None = None
    expression: list[str] | str | None = None
    expressionSource: str | None = None
    schemaName: str | None = None
    type: SourceType


class Partition(BaseModel):
    name: str
    mode: PartitionMode
    queryGroup: str | None = None
    source: Source


class Relationship(BaseModel):
    name: str
    annotations: list[dict] | None = None
    crossFilteringBehavior: str | None = None
    fromCardinality: str | None = None
    fromColumn: str
    fromTable: str
    securityFilteringBehavior: str | None = None
    joinOnDateBehavior: str | None = None
    isActive: bool | None = None
    toCardinality: str | None = None
    toColumn: str
    toTable: str


class Expression(BaseModel):
    name: str
    annotations: list[dict] | None = None
    description: str | None = None
    expression: list[str] | str
    sourceLineageTag: str | None = None
    kind: str | None = None
    lineageTag: str = Field(default_factory=lambda: str(uuid.uuid4()))
    mAttributes: str | None = None
    queryGroup: str | None = None


class Measure(BaseModel):
    name: str
    annotations: list[dict] | None = None
    changedProperties: Any | None = None
    dataCategory: DataCategory | None = None
    displayFolder: str | None = None
    expression: list[str] | str
    extendedProperties: list[dict] | None = None  # TODO: discover and implement
    formatString: str | None = None
    formatStringDefinition: dict | None = None
    lineageTag: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sourceLineageTag: str | None = None
    description: str | None = None
    isHidden: bool | None = None


class Column(BaseModel):
    name: str
    annotations: list[dict] | None = None
    changedProperties: Any | None = None
    dataCategory: DataCategory | None = None
    dataType: DataType | None = None
    expression: list[str] | str | None = None
    formatString: str | None = None
    extendedProperties: list[dict] | None = None
    isKey: bool | None = None
    isDataTypeInferred: bool | None = None
    isHidden: bool | None = None
    isNameInferred: bool | None = None
    isNullable: bool | None = None
    lineageTag: str = Field(default_factory=lambda: str(uuid.uuid4()))
    relatedColumnDetails: dict | None = None
    sortByColumn: str | None = None
    sourceColumn: str | None = None
    sourceLineageTag: str | None = None
    sourceProviderType: str | None = None
    summarizeBy: str | None = None
    type: ColumnType | None = None
    variations: list[dict] | None = None
    displayFolder: str | None = None


class Table(BaseModel):
    name: str
    annotations: list[dict] | None = None
    changedProperties: list[Any] | None = None
    calculationGroup: dict | None = None
    columns: list[Column] | None = None
    dataCategory: str | None = None
    excludeFromModelRefresh: bool | None = None
    hierarchies: list[dict] | None = None
    isHidden: bool | None = None
    isPrivate: bool | None = None
    lineageTag: str = Field(default_factory=lambda: str(uuid.uuid4()))
    measures: list[Measure] | None = None
    partitions: list[Partition]
    showAsVariationsOnly: bool | None = None
    sourceLineageTag: str | None = None
    description: str | None = None


class Model(BaseModel):
    annotations: list[dict] | None = None
    culture: str = "en-US"
    cultures: list[Culture] = [Culture()]
    dataAccessOptions: dict | None = None  # TODO: discover and implement
    defaultPowerBIDataSourceVesion: str = "powerBI_V3"
    discourageImplicitMeasures: bool | None = None
    expressions: list[Expression]
    maxParallelismPerRefresh: int | None = None
    queryGroups: Any | None = None
    relationships: list[Relationship] | None = None
    roles: list[dict] | None = None
    sourceQueryCulture: str = "en-US"
    tables: list[Table] | None = None


class SemanticModelDefinition(BaseModel):
    compatibilityLevel: int = 1600
    model: Model
    name: str | None
    path: str | None


class SemanticModel(BaseModel):
    item_definition: DefinitionPbism
    definition: SemanticModelDefinition
    platform: Platform

    @classmethod
    def read(cls, root_path: str) -> SemanticModel: ...
