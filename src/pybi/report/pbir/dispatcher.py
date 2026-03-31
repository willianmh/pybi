import re
from enum import Enum
from typing import Any

from pydantic import BaseModel, ValidationError

from .errors import UnsupportedReportSchemaVersionError

_SCHEMA_PATTERN = re.compile(
    r"/(?P<model_type>[^/]+)/(?P<version>\d+\.\d+\.\d+)/schema\.json$"
)


def strict_models_registry() -> dict[str, dict[str, type[BaseModel]]]:
    from .models.versionmetadata.v1_0_0 import VersionMetadata as VersionMetadataV100
    from .models.report.v3_0_0 import Report as ReportV300
    from .models.report.v3_1_0 import Report as ReportV310
    from .models.report.v3_2_0 import Report as ReportV320
    from .models.page.v1_4_0 import Page as PageV140
    from .models.page.v2_0_0 import Page as PageV200
    from .models.page.v2_1_0 import Page as PageV210
    from .models.pagesmetadata.v1_0_0 import PagesMetadata as PagesMetadataV100
    from .models.bookmark.v1_4_0 import Bookmark as BookmarkV140
    from .models.bookmark.v2_0_0 import Bookmark as BookmarkV200
    from .models.bookmark.v2_1_0 import Bookmark as BookmarkV210
    from .models.bookmarksmetadata.v1_0_0 import (
        BookmarksMetadata as BookmarkMetadataV100,
    )
    from .models.reportextension.v1_0_0 import ReportExtension as ReportExtensionV100
    from .models.visualcontainermobilestate.v2_2_0 import (
        VisualContainerMobileState as VisualContainerMobileStateV220,
    )
    from .models.visualcontainer.v2_3_0 import VisualContainer as VisualContainerV230
    from .models.visualcontainer.v2_4_0 import VisualContainer as VisualContainerV240
    from .models.visualcontainer.v2_5_0 import VisualContainer as VisualContainerV250
    from .models.visualcontainer.v2_6_0 import VisualContainer as VisualContainerV260
    from .models.visualcontainer.v2_7_0 import VisualContainer as VisualContainerV270

    return {
        "versionMetadata": {
            "1.0.0": VersionMetadataV100,
        },
        "report": {
            "3.0.0": ReportV300,
            "3.1.0": ReportV310,
            "3.2.0": ReportV320,
        },
        "page": {
            "1.4.0": PageV140,
            "2.0.0": PageV200,
            "2.1.0": PageV210,
        },
        "pagesMetadata": {
            "1.0.0": PagesMetadataV100,
        },
        "bookmark": {
            "1.4.0": BookmarkV140,
            "2.0.0": BookmarkV200,
            "2.1.0": BookmarkV210,
        },
        "bookmarksMetadata": {
            "1.0.0": BookmarkMetadataV100,
        },
        "reportExtension": {
            "1.0.0": ReportExtensionV100,
        },
        "visualContainerMobileState": {
            "2.2.0": VisualContainerMobileStateV220,
        },
        "visualContainer": {
            "2.3.0": VisualContainerV230,
            "2.4.0": VisualContainerV240,
            "2.5.0": VisualContainerV250,
            "2.6.0": VisualContainerV260,
            "2.7.0": VisualContainerV270,
        },
    }


class ParseMode(Enum):
    COMPATIBLE = 0
    STRICT = 1


def get_model_for_schema(
    schema_url: str | None,
    model_type: str,
    fallback_cls: type[BaseModel],
    parse_mode: ParseMode = ParseMode.COMPATIBLE,
) -> type[BaseModel]:
    if schema_url:
        match = _SCHEMA_PATTERN.search(schema_url)
        if match:
            url_model_type = match.group("model_type")
            version = match.group("version")

            if url_model_type != model_type:
                return fallback_cls

            registry = strict_models_registry()
            type_versions = registry.get(model_type, {})
            model_cls = type_versions.get(version)
            if model_cls is not None:
                return model_cls

            if parse_mode is ParseMode.STRICT:
                raise UnsupportedReportSchemaVersionError(
                    f"Unsupported `{model_type}` schema version: {version}"
                )

    if parse_mode is ParseMode.STRICT:
        raise UnsupportedReportSchemaVersionError(f"Missing `{model_type}` schema url.")
    return fallback_cls


def init_model(
    raw: dict[str, Any],
    model_type: str,
    fallback_cls: type[BaseModel],
    parse_mode: ParseMode = ParseMode.COMPATIBLE,
) -> BaseModel:
    schema_url = raw.get("$schema") if isinstance(raw, dict) else None
    model_cls = get_model_for_schema(
        schema_url=schema_url,
        model_type=model_type,
        fallback_cls=fallback_cls,
        parse_mode=parse_mode,
    )

    if model_cls is fallback_cls:
        return model_cls.model_validate(raw)

    try:
        return model_cls.model_validate(raw)
    except ValidationError:
        if parse_mode is ParseMode.STRICT:
            raise
        return fallback_cls.model_validate(raw)
