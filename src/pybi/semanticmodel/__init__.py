from __future__ import annotations

from pydantic import BaseModel, Field


class Column(BaseModel):
    name: str
    data_type: str = "string"
    is_key: bool = False
    format_string: str = ""
    summarize_by: str = "none"
    is_hidden: bool = False


class Measure(BaseModel):
    name: str
    expression: str
    display_folder: str = ""
    format_string: str = ""
    is_hidden: bool = False


class Table(BaseModel):
    name: str
    is_hidden: bool = False
    columns: list[Column] = Field(default_factory=list)
    measures: list[Measure] = Field(default_factory=list)


class Relationship(BaseModel):
    name: str
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    cross_filtering_behavior: str = "singleDirection"


class SemanticModel(BaseModel):
    name: str
    culture: str = "en-US"
    tables: list[Table] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)
