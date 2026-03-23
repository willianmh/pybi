from pydantic import BaseModel

from ..fabric.fabric import Platform, DefinitionPbir
from .legacy.legacy_model import ReportJsonDefinition
from .pbir.definition import PbirReportDefinition


class Report(BaseModel):
    item_definition: DefinitionPbir
    definition: ReportJsonDefinition | PbirReportDefinition
    platform: Platform
