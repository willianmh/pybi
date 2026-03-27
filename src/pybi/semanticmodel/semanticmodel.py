from pydantic import BaseModel, PrivateAttr

from ..fabric.fabric import DefinitionPbism, Platform
from .definition import SemanticModelDefinition
from .types import SemanticModelFormat


class SemanticModel(BaseModel):
    item_definition: DefinitionPbism
    definition: SemanticModelDefinition
    platform: Platform

    _ROOT_PATH: str | None = PrivateAttr(default="MyPowerBIDashboard.SemanticModel")
    _source_format: SemanticModelFormat | None = PrivateAttr(default=None)

    @classmethod
    def read(cls, root_path: str) -> SemanticModel:
        from ..serialization.strategies import TmdlStrategy, ModelBimStrategy
        from ..serialization.transport import LocalTransport
        from ..serialization.detect import detect_semantic_model_format

        fmt = detect_semantic_model_format(root_path=root_path)
        strategy = (
            TmdlStrategy() if fmt is SemanticModelFormat.TMDL else ModelBimStrategy()
        )
        transport = LocalTransport()

        parts = transport.read_parts(root_path)
        sm = strategy.deserialize(parts=parts)
        sm._ROOT_PATH = root_path
        sm._source_format = fmt
        return sm

    def write(
        self,
        root_path: str | None,
        format: SemanticModelFormat | None = None,
    ):
        from ..serialization.strategies import TmdlStrategy, ModelBimStrategy
        from ..serialization.transport import LocalTransport

        root_path = root_path or self._ROOT_PATH
        if not root_path:
            raise ValueError("You must provide a root_path.")

        fmt = format or self._source_format or SemanticModelFormat.TMDL
        strategy = (
            TmdlStrategy() if fmt is SemanticModelFormat.TMDL else ModelBimStrategy()
        )
        transport = LocalTransport()

        parts = strategy.serialize(self)
        transport.write_parts(parts, root_path)
