from pydantic import BaseModel


class ReportDefinition(BaseModel):
    FILENAME: str

    @property
    def sections(self) -> list: ...
