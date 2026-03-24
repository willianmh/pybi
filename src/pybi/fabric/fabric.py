from typing import ClassVar, Literal
import uuid

from pydantic import BaseModel, ConfigDict, Field, model_validator

FABRIC_SCHEMA_URL = "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json"
SM_SCHEMA_URL = "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json"


class ByConnection(BaseModel):
    connectionString: str
    pbiserviceModelId: int | None = None
    pbiModeVirtualServerName: str | None = None
    pbiModeDatabaseName: str | None = None
    name: str | None = None
    connectionType: str | None = None


class ByPath(BaseModel):
    path: str


class DatasetReference(BaseModel):
    byPath: ByPath | None = None
    byConnection: ByConnection | None = None

    @model_validator(mode="after")
    def only_one(self):
        if self.byPath is not None and self.byConnection is not None:
            raise ValueError("Provide only from `byPath` or `byConnection`")
        return self


# Platform


class Metadata(BaseModel):
    type: Literal["SemanticModel", "Report"] = Field(
        ..., description="The type of the item"
    )
    displayName: str = Field(
        ..., description="Name to be displayed in the Fabric Service"
    )
    description: str | None = Field(default=None, description="Object description")


class ConfigPlatform(BaseModel):
    version: str = "2.0"
    logicalId: str = Field(default_factory=lambda: str(uuid.uuid4()))


# Main Components


class DefinitionPbir(BaseModel):
    FILENAME: ClassVar[str] = "definition.pbir"
    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
        extra="forbid",
    )

    schema_: str = Field(default=SM_SCHEMA_URL, alias="$schema")
    version: str = "2.0"
    datasetReference: DatasetReference


class DefinitionPbism(BaseModel):
    FILENAME: ClassVar[str] = "definition.pbism"
    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
        extra="forbid",
    )

    schema_: str = Field(default=SM_SCHEMA_URL, alias="$schema")


class Platform(BaseModel):
    FILENAME: ClassVar[str] = ".platform"
    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
    )

    schema_: str = Field(default=FABRIC_SCHEMA_URL, alias="$schema")
    metadata: Metadata
    config: ConfigPlatform = Field(default_factory=ConfigPlatform)


def default_report_platform() -> Platform:
    return Platform(metadata=Metadata(type="Report", displayName="Report"))


def default_definition_pbir() -> DefinitionPbir:
    return DefinitionPbir(
        datasetReference=DatasetReference(byPath=ByPath(path="../This.SemanticModel"))
    )
