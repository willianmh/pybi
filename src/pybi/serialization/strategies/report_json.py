from ..types import Part
from ...report.legacy.legacy_model import ReportDefinition
from ...report.report import Report


class ReportJsonStrategy:
    def serialize(self, model: Report) -> list[Part]:
        parts: list[Part]

        report_payload = dump_json_bytes(model.definition)
        parts.append(Part(path=model.definition.FILENAME))
