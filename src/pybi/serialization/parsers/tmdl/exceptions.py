class TMDLError(Exception):
    """Base exception for TMDL parsing errors."""

    def __init__(
        self,
        message: str,
        line: int | None = None,
        column: int | None = None,
        file_path: str | None = None,
    ):
        self.message = message
        self.line = line
        self.column = column
        self.file_path = file_path
        super().__init__(self._format())

    def _format(self) -> str:
        location = ""
        if self.file_path:
            location += f"{self.file_path}"
        if self.line is not None:
            location += f":{self.line}"
        if self.column is not None:
            location += f":{self.column}"
        if location:
            location += ": "
        return f"{location}{self.message}"


class TMDLLexerError(TMDLError):
    """Exception raised during lexical analysis."""

    pass


class TMDLParseError(TMDLError):
    """Exception raised during parsing."""

    pass


class TMDLTransformError(TMDLError):
    """Exception raised during AST transformation to Pydantic models."""

    pass
