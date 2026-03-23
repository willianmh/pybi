from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ...formattingobjectdefinitions.v1_4_0.model import Selector


class VisualContainerGeneralFormattingObjects(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    x: object | None = None
    y: object | None = None
    width: object | None = None
    height: object | None = None
    altText: object | None = None
    allowBinnedLineSample: object | None = None
    allowOverlappingPointsSample: object | None = None
    keepLayerOrder: object | None = None


class VisualContainerGeneralItem(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    selector: Selector | None = None
    properties: VisualContainerGeneralFormattingObjects = Field(
        ...,
        description="Describes the properties of the object to apply formatting changes to.",
    )
