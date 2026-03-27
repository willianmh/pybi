from pydantic import BaseModel


class ReportDefinition(BaseModel):
    _FILENAME: str

    @property
    def sections(self) -> list: ...
