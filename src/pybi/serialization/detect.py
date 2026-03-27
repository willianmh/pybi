from pathlib import Path

from ..semanticmodel.types import SemanticModelFormat
from ..report.types import ReportFormat


def detect_semantic_model_format(root_path: str | Path) -> SemanticModelFormat:
    root = Path(root_path)

    definition_dir = root / SemanticModelFormat.TMDL.value
    model_bim = root / SemanticModelFormat.LEGACY.value

    if definition_dir.is_dir() and any(
        f.suffix == ".tmdl" for f in definition_dir.iterdir()
    ):
        return SemanticModelFormat.TMDL

    if model_bim.is_file():
        return SemanticModelFormat.LEGACY

    raise ValueError(f"Cannot detect Semantic Model format in {root}")


def detect_report_format(root_path: str | Path) -> ReportFormat:
    root = Path(root_path)

    definition_dir = root / ReportFormat.PBIR.value
    report_json = root / ReportFormat.LEGACY.value

    if definition_dir.is_dir() and any(
        f.suffix == ".json" for f in definition_dir.iterdir()
    ):
        return ReportFormat.PBIR

    if report_json.is_file():
        return ReportFormat.LEGACY

    raise ValueError(f"Cannot detect Report format in {root}")
