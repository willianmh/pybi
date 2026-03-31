import base64
from dataclasses import dataclass


@dataclass
class Part:
    """"""

    path: str
    payload: bytes

    @classmethod
    def from_text(cls, path: str, text: str, encoding: str = "utf-8") -> Part:
        return cls(path=path, payload=text.encode(encoding=encoding))

    @classmethod
    def from_base64(cls, path: str, b64: str) -> Part:
        return cls(path=path, payload=base64.b64decode(b64))

    def as_text(self, encoding: str = "utf-8") -> str:
        return self.payload.decode(encoding)
