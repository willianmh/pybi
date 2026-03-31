from ..base import PermissiveSchema


class PbirVersion(PermissiveSchema):
    version: str | None = None
