import os

from ..semanticmodel.types import SemanticModelFormat
from ..report.types import ReportFormat


def detect_semantic_model_format(root_path: str) -> SemanticModelFormat:
    definition_dir = os.path.join(root_path, "definition")
    model_bim = os.path.join(root_path, "model.bim")

    if os.path.isdir(definition_dir) and any(
        f.endswith(".tmdl") for f in os.listdir(definition_dir)
    ):
        return SemanticModelFormat.TMDL
    if os.path.isfile(model_bim):
        return SemanticModelFormat.LEGACY
    raise ValueError(f"Cannot detect Semantic Model format in {root_path}")


def detect_report_format(root_path: str) -> ReportFormat:
    definition_dir = os.path.join(root_path, "definition")
    report_json = os.path.join(root_path, "report.json")

    if os.path.isdir(definition_dir) and any(
        f.endswith(".json") for f in os.listdir(definition_dir)
    ):
        return ReportFormat.PBIR
    if os.path.isfile(report_json):
        return ReportFormat.LEGACY
    raise ValueError(f"Cannot detect Semantic Model format in {root_path}")
