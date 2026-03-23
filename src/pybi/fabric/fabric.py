from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

FABRIC_SCHEMA_URL = "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json"
SM_SCHEMA_URL = "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json"


class DefinitionPbir(BaseModel): ...


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
