from pydantic import BaseModel

from .semanticmodel import SemanticModel
from .report import Report


class PowerBI(BaseModel):
    report: Report
    semantic_model: SemanticModel
