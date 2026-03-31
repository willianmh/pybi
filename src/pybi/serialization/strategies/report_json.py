from ..types import Part
from ...report.report import Report
from ...report.pbir.definition import PbirReportDefinition
from ...report.legacy.legacy_model import ReportJsonDefinition
from ...fabric.fabric import (
    DefinitionPbir,
    Platform,
    default_definition_pbir,
    default_report_platform,
)
from .helpers import to_part, from_parts


class ReportJsonStrategy:
    def serialize(self, model: Report) -> list[Part]:
        parts: list[Part] = []
        if isinstance(model.definition, PbirReportDefinition):
            raise ValueError("Pbir cannot be serialized as report json.")

        parts.append(to_part(model.definition))
        parts.append(to_part(model.platform))
        parts.append(to_part(model.item_definition))

        static = getattr(model, "_static_resources", None)
        if static:
            for res_part in static:
                parts.append(res_part)

        return parts

    def deserialize(self, parts: list[Part]) -> Report:
        definition = from_parts(parts, ReportJsonDefinition)

        if not definition:
            raise ValueError("Report Json not found.")

        platform = from_parts(parts, Platform) or default_report_platform()
        item_definition = from_parts(parts, DefinitionPbir) or default_definition_pbir()

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

        return report
