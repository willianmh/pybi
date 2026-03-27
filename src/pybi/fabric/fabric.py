import os
from typing import ClassVar, Literal
import uuid

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, model_validator

FABRIC_SCHEMA_URL = "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json"
SM_SCHEMA_URL = "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json"


# pbip
class Report(BaseModel):
    path: str


class Artifact(BaseModel):
    report: Report


class Settings(BaseModel):
    enableAutoRecovery: bool


# Definition Pbism
class DatasetSettings(BaseModel):
    qnaEnabled: bool | None = None
    qnaLsdlSharingPermissions: int | None = None


# Definition Pbir


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

    def get_semantic_model_root_path(self) -> str | None:
        return self.byPath.path if self.byPath else None


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
    _FILENAME: ClassVar[str] = "definition.pbir"
    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
        extra="forbid",
    )

    schema_: str = Field(default=SM_SCHEMA_URL, alias="$schema")
    version: str = "2.0"
    datasetReference: DatasetReference

    def get_semantic_model_root_path(self) -> str | None:
        return self.datasetReference.get_semantic_model_root_path()


class DefinitionPbism(BaseModel):
    _FILENAME: ClassVar[str] = "definition.pbism"
    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
        extra="forbid",
    )

    schema_: str = Field(default=SM_SCHEMA_URL, alias="$schema")
    version: str = "2.0"
    settings: DatasetSettings = Field(default_factory=DatasetSettings)


class Platform(BaseModel):
    _FILENAME: ClassVar[str] = ".platform"
    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
    )

    schema_: str = Field(default=FABRIC_SCHEMA_URL, alias="$schema")
    metadata: Metadata
    config: ConfigPlatform = Field(default_factory=ConfigPlatform)


class PBIProject(BaseModel):
    version: str
    artifacts: list[Artifact]
    settings: Settings

    _PBIP_PATH: str | None = PrivateAttr(default=None)
    _FILENAME: str = PrivateAttr(default="MyPowerBIDashboard.pbip")

    @classmethod
    def read(cls, pbip_path: str) -> PBIProject:
        from ..serialization.strategies import PbipStrategy
        from ..serialization.transport import LocalTransport

        filename = os.path.basename(pbip_path)

        pbip_part = LocalTransport().read_part(pbip_path)
        pbip = PbipStrategy().deserialize([pbip_part])
        pbip._FILENAME = filename
        pbip._PBIP_PATH = pbip_path
        return pbip

    def write(self, pbip_path: str | None) -> None:
        from ..serialization.strategies import PbipStrategy
        from ..serialization.transport import LocalTransport

        pbip_path = pbip_path or self._PBIP_PATH
        if pbip_path is None:
            raise ValueError("You must provide a valid path.")

        self._FILENAME = os.path.basename(pbip_path)
        self._PBIP_PATH = pbip_path

        root_path = os.path.dirname(pbip_path)

        parts = PbipStrategy().serialize(self)
        LocalTransport().write_parts(parts, root_path)


# helpers


def default_semanticmodel_platform() -> Platform:
    return Platform(metadata=Metadata(type="Report", displayName="SM"))


def default_report_platform() -> Platform:
    return Platform(metadata=Metadata(type="Report", displayName="Report"))


def default_definition_pbir() -> DefinitionPbir:
    return DefinitionPbir(
        datasetReference=DatasetReference(byPath=ByPath(path="../This.SemanticModel"))
    )


def default_definition_pbism() -> DefinitionPbism:
    return DefinitionPbism()
