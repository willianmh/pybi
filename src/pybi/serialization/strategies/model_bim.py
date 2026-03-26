from ...fabric.fabric import (
    Platform,
    DefinitionPbism,
    default_definition_pbism,
    default_semanticmodel_platform,
)
from ...semanticmodel.semanticmodel import SemanticModel, SemanticModelDefinition
from ..types import Part
from .helpers import serialize_item, deserialize_item


class ModelBimStrategy:
    def serialize(self, model: SemanticModel) -> list[Part]:
        parts: list[Part] = []

        parts.extend(serialize_item(model.definition))
        parts.extend(serialize_item(model.platform))
        parts.extend(serialize_item(model.item_definition))

        return parts

    def deserialize(self, parts: list[Part]) -> SemanticModel:
        definition = deserialize_item(parts, SemanticModelDefinition)

        if not definition:
            raise ValueError("Semantic Model definition not found.")

        platform = deserialize_item(parts, Platform) or default_semanticmodel_platform()
        item_definition = (
            deserialize_item(parts, DefinitionPbism) or default_definition_pbism()
        )

        return SemanticModel(
            item_definition=item_definition,
            definition=definition,
            platform=platform,
        )
