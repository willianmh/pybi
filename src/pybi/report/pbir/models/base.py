from pydantic import BaseModel, ConfigDict, Field


class PermissiveSchema(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    field_schema: str | None = Field(None, alias="$schema")
