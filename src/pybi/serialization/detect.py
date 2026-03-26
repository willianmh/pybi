import os

from ..semanticmodel.types import SemanticModelFormat


def detect_from_disk(root: str) -> SemanticModelFormat:
    definition_dir = os.path.join(root, "definition")
    model_bim = os.path.join(root, "model.bim")

    if os.path.isdir(definition_dir) and any(
        f.endswith(".tmdl") for f in os.listdir(definition_dir)
    ):
        return SemanticModelFormat.TMDL
    if os.path.isfile(model_bim):
        return SemanticModelFormat.LEGACY
    raise ValueError(f"Cannot detect Semantic Model format in {root}")
