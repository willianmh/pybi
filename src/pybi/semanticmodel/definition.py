import uuid
from typing import Any, ClassVar

from pydantic import BaseModel, Field, model_validator

from .types import (
    Alignment,
    ColumnType,
    DataCategory,
    DataType,
    PartitionMode,
    SourceType,
    SummarizeBy,
)
from pybi.serialization.parsers.tmdl.grammar import ExpressionStyle, NameStyle


class ExpressionValue(BaseModel):
    """A TMDL expression: normalized content plus its serialisation style.

    ``value`` holds the expression text with structural TMDL tabs stripped
    (relative indentation, 0-based).  ``style`` records how it was read
    from TMDL, or how it should be written.

    Backward compatibility
    ----------------------
    Pydantic will coerce a plain ``str`` or ``list[str]`` to
    ``ExpressionValue`` via the ``model_validator``, so existing code that
    sets expression fields to raw strings continues to work.
    """

    value: str
    style: ExpressionStyle = ExpressionStyle.INLINE
    verbatim: bool = False

    @model_validator(mode="before")
    @classmethod
    def _coerce_from_raw(cls, data: Any) -> Any:
        """Accept str, list[str], or dict in addition to ExpressionValue."""
        if isinstance(data, str):
            lines = data.split("\n")
            style = ExpressionStyle.MULTILINE if len(lines) > 1 else ExpressionStyle.INLINE
            return {"value": data, "style": style}
        if isinstance(data, list):
            return {"value": "\n".join(data), "style": ExpressionStyle.MULTILINE}
        return data

    @classmethod
    def from_raw(
        cls, raw: "str | list[str] | ExpressionValue | None", style: ExpressionStyle = ExpressionStyle.INLINE
    ) -> "ExpressionValue | None":
        """Create an ExpressionValue from a raw string, list of lines, or existing instance."""
        if raw is None:
            return None
        if isinstance(raw, cls):
            return raw
        if isinstance(raw, list):
            return cls(value="\n".join(raw), style=style)
        return cls(value=raw, style=style)


class Annotation(BaseModel):
    """
    See: https://learn.microsoft.com/en-us/openspecs/sql_server_protocols/ms-ssas-t/7a16a837-cb88-4cb2-a766-a97c4d0e1f43
    See: https://docs.tabulareditor.com/en/api/TabularEditor.TOMWrapper.Annotation.html"""

    name: str | None = None
    value: str | None = None


class Variation(BaseModel):
    name: str | None = None
    annotations: Any | None = None
    isDefault: bool = False
    relationship: str | None = None
    defaultHierarchy: Any | None = None


class Culture(BaseModel):
    name: str = "en-US"
    linguisticMetadata: dict[str, Any] = {
        "content": {"Language": "en-US", "Version": "1.0.0"},
        "contentType": "json",
    }


class Source(BaseModel):
    entityName: str | None = None
    expression: ExpressionValue | None = None
    expressionSource: str | None = None
    schemaName: str | None = None
    type: SourceType


class Partition(BaseModel):
    name: str
    mode: PartitionMode
    queryGroup: str | None = None
    source: Source


class Relationship(BaseModel):
    """
    See: https://docs.tabulareditor.com/en/api/TabularEditor.TOMWrapper.SingleColumnRelationship.html
    See: https://docs.tabulareditor.com/en/api/TabularEditor.TOMWrapper.Relationship.html
    """

    name: str | None = None
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
    expression: ExpressionValue
    sourceLineageTag: str | None = None
    kind: str | None = None
    lineageTag: str = Field(default_factory=lambda: str(uuid.uuid4()))
    mAttributes: str | None = None
    queryGroup: str | None = None


class Measure(BaseModel):
    name: str | None = None
    name_style: NameStyle = NameStyle.UNQUOTED
    annotations: list[dict] | None = None
    changedProperties: Any | None = None
    dataCategory: DataCategory | None = None
    displayFolder: str | None = None
    expression: ExpressionValue | None = None
    extendedProperties: list[dict] | None = None  # TODO: discover and implement
    formatString: str | None = None
    formatStringDefinition: dict | None = None
    lineageTag: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sourceLineageTag: str | None = None
    description: str | None = None
    isHidden: bool | None = None


class Column(BaseModel):
    """
    See: https://docs.tabulareditor.com/en/api/TabularEditor.TOMWrapper.Column.html
    """

    name: str | None = None
    name_style: NameStyle = NameStyle.UNQUOTED
    annotations: list[dict] | None = None
    changedProperties: list[Any] | None = None
    dataCategory: DataCategory | None = None
    dataType: DataType | None = None
    expression: ExpressionValue | None = None
    formatString: str | None = None
    extendedProperties: list[dict] | None = None
    isKey: bool | None = None
    isDataTypeInferred: bool | None = None
    isHidden: bool | None = None
    isNameInferred: bool | None = None
    isNullable: bool | None = None
    lineageTag: str = Field(default_factory=lambda: str(uuid.uuid4()))
    alignment: Alignment | None = None
    relatedColumnDetails: dict | str | None = None
    sortByColumn: str | None = None
    sourceColumn: str | None = None
    sourceLineageTag: str | None = None
    sourceProviderType: str | None = None
    summarizeBy: SummarizeBy | None = "default"
    type: ColumnType | None = None
    variations: list[Variation] | None = None
    displayFolder: str | None = None


class Table(BaseModel):
    name: str
    annotations: list[dict] | None = None
    changedProperties: list[Any] | None = None
    calculationGroup: dict | list | None = None
    columns: list[Column] | None = None
    dataCategory: str | None = None
    excludeFromModelRefresh: bool | None = None
    hierarchies: list[dict] | None = None
    isHidden: bool | None = None
    isPrivate: bool | None = None
    lineageTag: str = Field(default_factory=lambda: str(uuid.uuid4()))
    measures: list[Measure] | None = None
    partitions: list[Partition] = Field(default_factory=list)
    showAsVariationsOnly: bool | None = None
    sourceLineageTag: str | None = None
    description: str | None = None


class TablePermission(BaseModel):
    name: str
    filterExpression: ExpressionValue | None = None


class Role(BaseModel):
    name: str
    modelPermission: str | None = None
    tablePermissions: list[TablePermission] | None = None
    annotations: list[dict] | None = None


class Model(BaseModel):
    annotations: list[dict] | None = None
    culture: str = "en-US"
    cultures: list[Culture] = [Culture()]
    dataAccessOptions: dict | None = None  # TODO: discover and implement
    defaultPowerBIDataSourceVersion: str = "powerBI_V3"
    discourageImplicitMeasures: bool | None = None
    expressions: list[Expression] = Field(default_factory=list)
    maxParallelismPerRefresh: int | None = None
    queryGroups: Any | None = None
    relationships: list[Relationship] | None = None
    roles: list["Role"] | None = None
    sourceQueryCulture: str = "en-US"
    tables: list[Table] | None = None


class SemanticModelDefinition(BaseModel):
    _FILENAME: ClassVar[str] = "model.bim"
    compatibilityLevel: int = 1600
    model: Model
