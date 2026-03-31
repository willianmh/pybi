from ...fabric.fabric import PBIProject
from ...serialization.types import Part
from ...serialization.strategies.helpers import to_part, from_parts


def _find_pbip_part(parts: list[Part]) -> Part | None:
    for part in parts:
        if part.path.endswith(".pbip"):
            return part
    return None


class PbipStrategy:
    def serialize(self, model: PBIProject) -> list[Part]:
        return [to_part(model)]

    def deserialize(self, parts: list[Part]) -> PBIProject:
        p = _find_pbip_part(parts)
        if p is None:
            raise ValueError(".pbip file not found.")

        pbip = from_parts(parts, model_type=PBIProject, path=p.path)
        return PBIProject.model_validate(pbip)
