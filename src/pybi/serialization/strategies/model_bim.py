from ...fabric.fabric import (
    Platform,
    DefinitionPbism,
    default_definition_pbism,
    default_semanticmodel_platform,
)
from ...semanticmodel.semanticmodel import SemanticModel, SemanticModelDefinition
from ..types import Part
from .helpers import to_part, from_parts


class ModelBimStrategy:
    def serialize(self, model: SemanticModel) -> list[Part]:
        return [
            to_part(model.definition),
            to_part(model.platform),
            to_part(model.item_definition),
        ]

    def deserialize(self, parts: list[Part]) -> SemanticModel:
        definition = from_parts(parts, SemanticModelDefinition)

        if not definition:
            raise ValueError("Semantic Model definition not found.")

        platform = from_parts(parts, Platform) or default_semanticmodel_platform()
        item_definition = (
            from_parts(parts, DefinitionPbism) or default_definition_pbism()
        )

        return SemanticModel(
            item_definition=item_definition,
            definition=definition,
            platform=platform,
        )
