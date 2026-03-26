from ...fabric.fabric import (
    Platform,
    DefinitionPbism,
    default_definition_pbism,
    default_semanticmodel_platform,
)
from ...semanticmodel.semanticmodel import SemanticModel, SemanticModelDefinition
from ..types import Part
from ..parsers.tmdl.loader import TMDLPartsLoader
from ..parsers.tmdl.writer import TMDLPartsWriter
from ..parsers.tmdl.grammar import DEFINITION_PREFIX
from .helpers import serialize_item, deserialize_item


class TmdlStrategy:
    def serialize(self, model: SemanticModel) -> list[Part]:
        parts: list[Part] = []

        tmdl_files = TMDLPartsWriter().write(model.definition)
        for rel_path, text in tmdl_files.items():
            parts.append(Part.from_text(f"{DEFINITION_PREFIX}{rel_path}", text))

        parts.extend(serialize_item(model.platform))
        parts.extend(serialize_item(model.item_definition))

        return parts

    def deserialize(self, parts: list[Part]) -> SemanticModel:
        tmdl_files: dict[str, str] = {}

        for p in parts:
            if p.path.startswith(DEFINITION_PREFIX) and p.path.endswith(".tmdl"):
                key = p.path[len(DEFINITION_PREFIX) :]
                tmdl_files[key] = p.as_text()

        model_data = TMDLPartsLoader(tmdl_files).load()
        definition = SemanticModelDefinition(**model_data)

        platform = deserialize_item(parts, Platform) or default_semanticmodel_platform()
        item_definition = (
            deserialize_item(parts, DefinitionPbism) or default_definition_pbism()
        )

        return SemanticModel(
            item_definition=item_definition,
            definition=definition,
            platform=platform,
        )
