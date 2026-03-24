import json

from pydantic import BaseModel

from ..types import Part
from ...report.report import Report
from ...report.legacy.legacy_model import ReportJsonDefinition
from ...fabric.fabric import (
    DefinitionPbir,
    Platform,
    default_definition_pbir,
    default_report_platform,
)


def dump_json_bytes(
    model: BaseModel,
    exclude: set[str] | None = None,
    exclude_none: bool = True,
    exclude_unset: bool = True,
    by_alias: bool = True,
    indent: int = 2,
    encoding: str = "utf-8",
) -> bytes:
    data = model.model_dump(
        mode="json",
        exclude_none=exclude_none,
        exclude_unset=exclude_unset,
        by_alias=by_alias,
        exclude=exclude,
    )
    text = json.dumps(data, indent=indent)
    return text.encode(encoding)


def find_part(parts: list[Part], path: str) -> Part | None:
    for p in parts:
        if p.path == path:
            return p
    return None


class ReportJsonStrategy:
    def serialize(self, model: Report) -> list[Part]:
        parts: list[Part] = []

        report_payload = dump_json_bytes(model.definition)
        parts.append(Part(path=model.definition.FILENAME, payload=report_payload))

        if model.platform is not None:
            payload = dump_json_bytes(model.platform)
            parts.append(Part(path=model.platform.FILENAME, payload=payload))

        if model.item_definition is not None:
            payload = dump_json_bytes(model.item_definition)
            parts.append(Part(path=model.item_definition.FILENAME, payload=payload))

        # get if attached
        static = getattr(model, "_static_resources", None)
        if static:
            for res_part in static:
                parts.append(res_part)

        return parts

    def deserialize(self, parts: list[Part]) -> Report:
        report_part = find_part(parts=parts, path=ReportJsonDefinition.FILENAME)
        if report_part is None:
            raise ValueError(f"Part {ReportJsonDefinition.FILENAME} not found")

        report_data = json.loads(report_part.payload)
        definition = ReportJsonDefinition(**report_data)

        platform_part = find_part(parts=parts, path=Platform.FILENAME)
        if platform_part:
            platform_data = json.loads(platform_part.payload)
            platform = Platform(**platform_data)
        else:
            platform = default_report_platform()

        pbir_part = find_part(parts=parts, path=DefinitionPbir.FILENAME)
        if pbir_part:
            pbir_data = json.loads(pbir_part.payload)
            item_definition = DefinitionPbir(**pbir_data)
        else:
            item_definition = default_definition_pbir()

        report = Report(
            item_definition=item_definition,
            definition=definition,
            platform=platform,
        )

        static = [
            p
            for p in parts
            if p.path.startswith("StaticResources/")
            or p.path.startswith("staticResources/")
        ]
        # TODO: add attr to class
        if static:
            object.__setattr__(report, "_static_resources", static)
