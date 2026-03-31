from typing import Any

from ..base import PermissiveSchema


class PbirBookmark(PermissiveSchema):
    """Permissive Bookmark definition"""

    name: str = ""
    displayName: str = ""
    options: dict[str, Any] | None = None
    explorationState: dict[str, Any] | None = None
