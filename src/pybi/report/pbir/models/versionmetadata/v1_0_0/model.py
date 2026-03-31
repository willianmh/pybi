# generated manually by datamodel-codegen:
#   filename:  schema.json


from typing import Literal, Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class VersionMetadata(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    field_schema: Literal[
        "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json"
    ] = Field(
        ..., alias="$schema", description="Defines the schema to use for an item."
    )
    version: Annotated[
        str, StringConstraints(pattern=r"^[1-9][0-9]*\.(0|[1-9][0-9]*)\.0$")
    ] = Field(
        ...,
        description="Defines the report definition version, format of version is major.minor.patch\n- major: >=1\n- minor: >=0\n- patch: always 0",
    )
