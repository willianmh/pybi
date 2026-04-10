from ..base import PermissiveSchema


class PbirBookmarksMetadata(PermissiveSchema):
    """Permissive Bookmark definition"""

    items: list | None = None
