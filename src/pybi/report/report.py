from pathlib import Path

from pydantic import BaseModel, PrivateAttr

from ..fabric.fabric import Platform, DefinitionPbir
from .legacy.legacy_model import ReportJsonDefinition
from .pbir.definition import PbirReportDefinition
from .types import ReportFormat


class Report(BaseModel):
    item_definition: DefinitionPbir
    definition: ReportJsonDefinition | PbirReportDefinition
    platform: Platform

    _ROOT_PATH: str | None = PrivateAttr(default="MyPowerBIDashboard.Report")
    _source_format: ReportFormat | None = PrivateAttr(default=None)

    @classmethod
    def read(cls, root_path: str | Path) -> Report:
        from ..serialization.strategies import PbirStrategy, ReportJsonStrategy
        from ..serialization.transport import LocalTransport
        from ..serialization.detect import detect_report_format

        fmt = detect_report_format(root_path=root_path)
        strategy = PbirStrategy() if fmt is ReportFormat.PBIR else ReportJsonStrategy()
        transport = LocalTransport()

        parts = transport.read_parts(root=root_path)
        report = strategy.deserialize(parts=parts)
        report._ROOT_PATH = str(root_path)
        report._source_format = fmt
        return report

    def write(
        self,
        root_path: str | Path | None,
        format: ReportFormat | None,
    ):
        from ..serialization.strategies import PbirStrategy, ReportJsonStrategy
        from ..serialization.transport import LocalTransport

        root_path = root_path or self._ROOT_PATH
        if not root_path:
            raise ValueError("You must provide a root_path.")

        if format is not None and self._source_format is not None:
            if format != self._source_format:
                raise ValueError(
                    f"ReportJson and PBIR are not conversible, the report was loaded as `{self._source_format}`, not possible to write as `{format}`"
                )

        fmt = format or self._source_format or ReportFormat.PBIR
        strategy = PbirStrategy() if fmt is ReportFormat.PBIR else ReportJsonStrategy()
        transport = LocalTransport()

        parts = strategy.serialize(self)
        transport.write_parts(parts, root_path)
