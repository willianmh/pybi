from pydantic import BaseModel


class ReportDefinition(BaseModel):
    _FILENAME: str

    @property
    def pages(self) -> list: ...
