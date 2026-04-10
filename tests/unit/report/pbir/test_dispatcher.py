from unittest.mock import patch

import pytest
from pydantic import BaseModel

from pybi.report.pbir.dispatcher import ParseMode, get_model_for_schema
from pybi.report.pbir.errors import UnsupportedReportSchemaVersionError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FallbackModel(BaseModel):
    pass


class ReportV300(BaseModel):
    pass


class ReportV999(BaseModel):
    pass


_FAKE_REGISTRY = {
    "report": {
        "3.0.0": ReportV300,
        "9.9.9": ReportV999,
    },
}

# A valid schema URL whose model_type and version exist in the fake registry
KNOWN_URL = "https://example.com/report/3.0.0/schema.json"
UNKNOWN_VERSION_URL = "https://example.com/report/0.0.1/schema.json"
WRONG_TYPE_URL = "https://example.com/page/3.0.0/schema.json"
NO_MATCH_URL = "https://example.com/no-pattern-here"


@pytest.fixture(autouse=True)
def patch_registry():
    with patch(
        "pybi.report.pbir.dispatcher.strict_models_registry",
        return_value=_FAKE_REGISTRY,
    ):
        yield


# ---------------------------------------------------------------------------
# schema_url=None or falsy
# ---------------------------------------------------------------------------


class TestFalsySchemaUrl:
    def test_none_compatible_returns_fallback(self):
        result = get_model_for_schema(
            None, "report", FallbackModel, ParseMode.COMPATIBLE
        )
        assert result is FallbackModel

    def test_none_strict_raises(self):
        with pytest.raises(UnsupportedReportSchemaVersionError, match="Missing"):
            get_model_for_schema(None, "report", FallbackModel, ParseMode.STRICT)

    def test_empty_string_compatible_returns_fallback(self):
        result = get_model_for_schema("", "report", FallbackModel, ParseMode.COMPATIBLE)
        assert result is FallbackModel

    def test_empty_string_strict_raises(self):
        with pytest.raises(UnsupportedReportSchemaVersionError, match="Missing"):
            get_model_for_schema("", "report", FallbackModel, ParseMode.STRICT)


# ---------------------------------------------------------------------------
# URL that doesn't match the pattern
# ---------------------------------------------------------------------------


class TestUrlPatternMismatch:
    def test_no_pattern_match_compatible_returns_fallback(self):
        result = get_model_for_schema(
            NO_MATCH_URL, "report", FallbackModel, ParseMode.COMPATIBLE
        )
        assert result is FallbackModel

    def test_no_pattern_match_strict_raises_missing(self):
        with pytest.raises(UnsupportedReportSchemaVersionError, match="Missing"):
            get_model_for_schema(
                NO_MATCH_URL, "report", FallbackModel, ParseMode.STRICT
            )


# ---------------------------------------------------------------------------
# URL model_type doesn't match the requested model_type
# ---------------------------------------------------------------------------


class TestModelTypeMismatch:
    def test_type_mismatch_compatible_returns_fallback(self):
        result = get_model_for_schema(
            WRONG_TYPE_URL, "report", FallbackModel, ParseMode.COMPATIBLE
        )
        assert result is FallbackModel

    def test_type_mismatch_strict_still_returns_fallback(self):
        # STRICT only raises for missing/unknown versions: a type mismatch is
        # treated as "not my URL" and falls back immediately, even in strict mode.
        result = get_model_for_schema(
            WRONG_TYPE_URL, "report", FallbackModel, ParseMode.STRICT
        )
        assert result is FallbackModel


# ---------------------------------------------------------------------------
# Known URL: version found in registry
# ---------------------------------------------------------------------------


class TestKnownVersion:
    def test_compatible_returns_registered_class(self):
        result = get_model_for_schema(
            KNOWN_URL, "report", FallbackModel, ParseMode.COMPATIBLE
        )
        assert result is ReportV300

    def test_strict_returns_registered_class(self):
        result = get_model_for_schema(
            KNOWN_URL, "report", FallbackModel, ParseMode.STRICT
        )
        assert result is ReportV300


# ---------------------------------------------------------------------------
# URL version not in registry
# ---------------------------------------------------------------------------


class TestUnknownVersion:
    def test_compatible_returns_fallback(self):
        result = get_model_for_schema(
            UNKNOWN_VERSION_URL, "report", FallbackModel, ParseMode.COMPATIBLE
        )
        assert result is FallbackModel

    def test_strict_raises_with_version_in_message(self):
        with pytest.raises(UnsupportedReportSchemaVersionError, match="0.0.1"):
            get_model_for_schema(
                UNKNOWN_VERSION_URL, "report", FallbackModel, ParseMode.STRICT
            )

    def test_strict_raises_with_model_type_in_message(self):
        with pytest.raises(UnsupportedReportSchemaVersionError, match="report"):
            get_model_for_schema(
                UNKNOWN_VERSION_URL, "report", FallbackModel, ParseMode.STRICT
            )


# ---------------------------------------------------------------------------
# model_type known in URL but not present in registry at all
# ---------------------------------------------------------------------------


class TestModelTypeNotInRegistry:
    def test_compatible_returns_fallback(self):
        url = "https://example.com/unknownModel/1.0.0/schema.json"
        result = get_model_for_schema(
            url, "unknownModel", FallbackModel, ParseMode.COMPATIBLE
        )
        assert result is FallbackModel

    def test_strict_raises(self):
        url = "https://example.com/unknownModel/1.0.0/schema.json"
        with pytest.raises(UnsupportedReportSchemaVersionError):
            get_model_for_schema(url, "unknownModel", FallbackModel, ParseMode.STRICT)


# ---------------------------------------------------------------------------
# Default parse_mode is COMPATIBLE
# ---------------------------------------------------------------------------


class TestDefaultParseMode:
    def test_default_is_compatible(self):
        # With a None URL and no explicit parse_mode, should return fallback (not raise)
        result = get_model_for_schema(None, "report", FallbackModel)
        assert result is FallbackModel
