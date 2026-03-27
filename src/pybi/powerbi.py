import logging

from pydantic import BaseModel
from pathlib import Path

from .fabric import PBIProject
from .report import Report
from .semanticmodel import SemanticModel

from .report.types import ReportFormat
from .semanticmodel.types import SemanticModelFormat


logger = logging.getLogger(__name__)


class PowerBI(BaseModel):
    name: str | None = None
    root_path: str | None = None
    report: Report | None = None
    semantic_model: SemanticModel | None = None
    pbip: PBIProject | None = None

    @classmethod
    def read(cls, root_path: str) -> PowerBI:
        """Read a folder, detect pbip, if there is a .pbip then call `.from_pbip`, otherwise try to parse .Report and .SemanticModel folder"""
        ...

    @classmethod
    def from_pbip(cls, pbip_path: str) -> PowerBI:
        p = Path(pbip_path)
        name = p.stem
        root_path = p.parent

        pbip = PBIProject.read(pbip_path)

        report_root_path = root_path / pbip.artifacts[0].report.path
        # logger.info(f"report_root_path: {report_root_path}")

        report = Report.read(str(report_root_path))
        semantic_model_root_path = report.item_definition.get_semantic_model_root_path()

        semantic_model = None
        if semantic_model_root_path:
            semantic_model_root_path = report_root_path / semantic_model_root_path
            semantic_model = SemanticModel.read(str(semantic_model_root_path))

        return PowerBI(
            name=name,
            root_path=str(root_path),
            report=report,
            semantic_model=semantic_model,
            pbip=pbip,
        )

    def write(
        self,
        root_path: str | None = None,
        semantic_model_format: SemanticModelFormat | None = None,
        report_format: ReportFormat | None = None,
    ):
        root_path = root_path or self.root_path
        if root_path is None:
            raise ValueError("You must provide a root path.")
        if self.report:
            report_root_path = f"{root_path}/{self.name}.Report/"
            self.report.write(report_root_path, report_format)

        if self.semantic_model:
            sm_root_path = f"{root_path}/{self.name}.SemanticModel/"
            self.semantic_model.write(sm_root_path, semantic_model_format)
        elif semantic_model_format:
            logger.warning(
                f"semantic_model_format passed `{semantic_model_format}` but PowerBI Dashboard has no SemanticModel. Ignoring it..."
            )

        if self.pbip:
            pbip_path = f"{root_path}/{self.name}.pbip"
            self.pbip.write(pbip_path)
