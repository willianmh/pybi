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
        """Read a project folder.

        Detection order:

        1. If the folder contains a ``*.pbip`` file, delegate to
           :meth:`from_pbip` (which also loads the linked report and semantic
           model).
        2. Otherwise scan for sub-folders whose names end with ``.Report`` and
           ``.SemanticModel`` and load whichever are found.

        Raises ``ValueError`` when *root_path* does not exist or is not a
        directory.
        """
        p = Path(root_path)
        if not p.is_dir():
            raise ValueError(f"Path {root_path!r} is not a directory.")

        pbip_files = sorted(p.glob("*.pbip"))
        if len(pbip_files) > 1:
            raise ValueError(
                f"Found {len(pbip_files)} .pbip files in {root_path!r}; "
                "expected exactly one. Specify the file directly via from_pbip()."
            )
        if pbip_files:
            return cls.from_pbip(str(pbip_files[0]))

        report_dirs = sorted(
            [d for d in p.iterdir() if d.is_dir() and d.name.endswith(".Report")]
        )
        sm_dirs = sorted(
            [d for d in p.iterdir() if d.is_dir() and d.name.endswith(".SemanticModel")]
        )

        if len(report_dirs) > 1:
            raise ValueError(
                f"Found {len(report_dirs)} .Report folders in {root_path!r}; "
                "expected at most one."
            )
        if len(sm_dirs) > 1:
            raise ValueError(
                f"Found {len(sm_dirs)} .SemanticModel folders in {root_path!r}; "
                "expected at most one."
            )

        name: str | None = None
        report = None
        semantic_model = None

        if report_dirs:
            report = Report.read(str(report_dirs[0]))
            name = report_dirs[0].name.removesuffix(".Report")

        if sm_dirs:
            semantic_model = SemanticModel.read(str(sm_dirs[0]))
            if name is None:
                name = sm_dirs[0].name.removesuffix(".SemanticModel")

        return PowerBI(
            name=name,
            root_path=str(root_path),
            report=report,
            semantic_model=semantic_model,
        )

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
