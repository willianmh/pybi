"""TMDL grammar constants, structure registry, and shared operations.

Single source of truth for all TMDL grammar-level definitions:
- Token-level constants (keywords, flags, character sets)
- Property name enums grouped by TMDL object type
- Syntax token constants
- Definition folder/file structure registry
- Shared name quoting/unquoting and column reference operations
"""

import re
from enum import Enum

# ---------------------------------------------------------------------------
# 1a. Token-level constants
# ---------------------------------------------------------------------------

# TMDL keywords that introduce object declarations
KEYWORDS = frozenset(
    {
        "database",
        "model",
        "table",
        "column",
        "measure",
        "partition",
        "relationship",
        "expression",
        "cultureInfo",
        "annotation",
        "ref",
        "source",
        "variation",
        "hierarchy",
        "level",
        "role",
        "tablePermission",
        "changedProperty",
        "formatStringDefinition",
        "extendedProperty",
        "calculationGroup",
        "calculationItem",
        "dataAccessOptions",
        "queryGroup",
    }
)

# Property names that act as boolean flags when present without a value
FLAG_PROPERTIES = frozenset(
    {
        "isHidden",
        "isKey",
        "isNullable",
        "isActive",
        "isDefault",
        "isPrivate",
        "isDataTypeInferred",
        "isNameInferred",
        "fastCombine",
        "legacyRedirects",
        "returnErrorValuesAsNull",
        "excludeFromModelRefresh",
        "showAsVariationsOnly",
        "discourageImplicitMeasures",
    }
)

# Characters allowed in unquoted identifiers (beyond alphanumeric)
IDENTIFIER_CONTINUATION_CHARS = frozenset("_-/+.\\@")

# Characters that force a name to be single-quoted per TMDL spec
SPECIAL_CHARS_REQUIRE_QUOTE = frozenset(" .=:'")

# ---------------------------------------------------------------------------
# 1a-ii. TMDL syntax token constants
# ---------------------------------------------------------------------------

BACKTICK_EXPR = "```"
BACKTICK_ASSIGN = "= ```"
# Space-insensitive pattern: matches '=' followed by optional whitespace then ```
# Used by the lexer so that '=```' and '=   ```' are both recognised correctly.
BACKTICK_ASSIGN_RE: re.Pattern[str] = re.compile(r"=\s*```")
DESCRIPTION_PREFIX = "///"

# ---------------------------------------------------------------------------
# 1a-iii. Property name enums grouped by TMDL object type
# ---------------------------------------------------------------------------


class ColumnProp(str, Enum):
    DATA_TYPE = "dataType"
    IS_HIDDEN = "isHidden"
    IS_KEY = "isKey"
    IS_NULLABLE = "isNullable"
    FORMAT_STRING = "formatString"
    LINEAGE_TAG = "lineageTag"
    SOURCE_LINEAGE_TAG = "sourceLineageTag"
    DATA_CATEGORY = "dataCategory"
    SUMMARIZE_BY = "summarizeBy"
    IS_NAME_INFERRED = "isNameInferred"
    SOURCE_COLUMN = "sourceColumn"
    SORT_BY_COLUMN = "sortByColumn"
    DISPLAY_FOLDER = "displayFolder"
    EXPRESSION = "expression"


class MeasureProp(str, Enum):
    FORMAT_STRING = "formatString"
    DISPLAY_FOLDER = "displayFolder"
    LINEAGE_TAG = "lineageTag"
    SOURCE_LINEAGE_TAG = "sourceLineageTag"
    DATA_CATEGORY = "dataCategory"
    IS_HIDDEN = "isHidden"
    EXPRESSION = "expression"


class RelationshipProp(str, Enum):
    FROM_COLUMN = "fromColumn"
    TO_COLUMN = "toColumn"
    IS_ACTIVE = "isActive"
    CROSS_FILTERING_BEHAVIOR = "crossFilteringBehavior"
    FROM_CARDINALITY = "fromCardinality"
    TO_CARDINALITY = "toCardinality"
    SECURITY_FILTERING_BEHAVIOR = "securityFilteringBehavior"
    JOIN_ON_DATE_BEHAVIOR = "joinOnDateBehavior"


class TableProp(str, Enum):
    SHOW_AS_VARIATIONS_ONLY = "showAsVariationsOnly"
    LINEAGE_TAG = "lineageTag"
    SOURCE_LINEAGE_TAG = "sourceLineageTag"
    IS_HIDDEN = "isHidden"
    IS_PRIVATE = "isPrivate"
    EXCLUDE_FROM_MODEL_REFRESH = "excludeFromModelRefresh"


class ExpressionProp(str, Enum):
    LINEAGE_TAG = "lineageTag"
    QUERY_GROUP = "queryGroup"
    KIND = "kind"


class PartitionProp(str, Enum):
    MODE = "mode"
    TYPE = "type"
    ENTITY_NAME = "entityName"
    EXPRESSION_SOURCE = "expressionSource"
    QUERY_GROUP = "queryGroup"


class ModelProp(str, Enum):
    CULTURE = "culture"
    SOURCE_QUERY_CULTURE = "sourceQueryCulture"
    COMPATIBILITY_LEVEL = "compatibilityLevel"
    DEFAULT_POWER_BI_DATA_SOURCE_VERSION = "defaultPowerBIDataSourceVersion"
    DISCOURAGE_IMPLICIT_MEASURES = "discourageImplicitMeasures"


class VariationProp(str, Enum):
    IS_DEFAULT = "isDefault"
    RELATIONSHIP = "relationship"
    DEFAULT_HIERARCHY = "defaultHierarchy"


class HierarchyProp(str, Enum):
    LINEAGE_TAG = "lineageTag"
    SOURCE_LINEAGE_TAG = "sourceLineageTag"


class LevelProp(str, Enum):
    ORDINAL = "ordinal"
    COLUMN = "column"
    LINEAGE_TAG = "lineageTag"
    SOURCE_LINEAGE_TAG = "sourceLineageTag"


class CultureProp(str, Enum):
    CONTENT_TYPE = "contentType"


# ---------------------------------------------------------------------------
# 1b. TMDL definition structure registry
# ---------------------------------------------------------------------------

# Top-level files (relative to definition/)
DEFINITION_FILES: dict[str, str] = {
    "database": "database.tmdl",
    "model": "model.tmdl",
    "relationships": "relationships.tmdl",
    "expressions": "expressions.tmdl",
}

# Subfolders containing one .tmdl file per item (relative to definition/)
DEFINITION_FOLDERS: dict[str, str] = {
    "tables": "tables",
    "cultures": "cultures",
}

# Prefix used by the persistence layer to namespace TMDL parts
DEFINITION_PREFIX = "definition/"

# ---------------------------------------------------------------------------
# 1c. Shared name operations
# ---------------------------------------------------------------------------


def quote_name(name: str) -> str:
    """Quote a name with single quotes if it contains special characters.

    Per TMDL spec, names must be quoted when they contain: . = : ' or whitespace,
    or when the first character is a digit.  Inner single quotes are escaped by
    doubling (e.g., ``It's`` → ``'It''s'``).
    """
    if not name:
        return name

    needs_quote = any(c in SPECIAL_CHARS_REQUIRE_QUOTE for c in name)
    if not needs_quote and name[0].isdigit():
        needs_quote = True

    if needs_quote:
        escaped = name.replace("'", "''")
        return f"'{escaped}'"
    return name


def unquote_name(name: str | None) -> str | None:
    """Remove surrounding single quotes from a TMDL name.

    Also un-escapes doubled single quotes inside (``''`` → ``'``).
    Returns the input unchanged when it is not quoted.
    """
    if not name:
        return name
    if name.startswith("'") and name.endswith("'") and len(name) > 2:
        return name[1:-1].replace("''", "'")
    return name


# ---------------------------------------------------------------------------
# 1c. Shared column-reference operations
# ---------------------------------------------------------------------------

# Pre-compiled patterns for the four quoting variants of Table.Column
_RE_BOTH_QUOTED = re.compile(r"'([^']+)'\.'([^']+)'")
_RE_TABLE_QUOTED = re.compile(r"'([^']+)'\.([^.]+)$")
_RE_COLUMN_QUOTED = re.compile(r"([^.]+)\.'([^']+)'")


def parse_column_reference(ref: str) -> tuple[str, str]:
    """Parse a TMDL column reference into ``(table, column)``.

    Handles all four quoting variants::

        'Table Name'.'Column Name'   → ("Table Name", "Column Name")
        'Table Name'.Column          → ("Table Name", "Column")
        Table.'Column Name'          → ("Table", "Column Name")
        Table.Column                 → ("Table", "Column")
    """
    if not ref:
        return "", ""

    m = _RE_BOTH_QUOTED.match(ref)
    if m:
        return m.group(1), m.group(2)

    m = _RE_TABLE_QUOTED.match(ref)
    if m:
        return m.group(1), m.group(2)

    m = _RE_COLUMN_QUOTED.match(ref)
    if m:
        return m.group(1), m.group(2)

    parts = ref.split(".", 1)
    if len(parts) == 2:
        return parts[0], parts[1]

    return ref, ""


def format_column_reference(ref: str) -> str:
    """Format a ``Table.Column`` reference with proper TMDL quoting.

    Parses the reference, quotes table/column names that need it, and
    reassembles to a canonical form.
    """
    if not ref or "." not in ref:
        return ref

    # First, parse the reference to extract raw table and column
    # Handle already-quoted table part
    if ref.startswith("'"):
        close_idx = ref.find("'", 1)
        if close_idx == -1:
            return ref
        # Skip escaped quotes ''
        while close_idx < len(ref) - 1 and ref[close_idx + 1] == "'":
            close_idx = ref.find("'", close_idx + 2)
            if close_idx == -1:
                return ref
        if close_idx + 1 >= len(ref) or ref[close_idx + 1] != ".":
            return ref
        table_part = ref[: close_idx + 1]  # Already quoted
        col_name = ref[close_idx + 2 :]
    else:
        dot_idx = ref.find(".")
        if dot_idx == -1:
            return ref
        table_part = ref[:dot_idx]
        col_name = ref[dot_idx + 1 :]

    # If column is already quoted, pass through
    if col_name.startswith("'") and col_name.endswith("'"):
        return f"{table_part}.{col_name}"

    # Quote the column name if needed
    if col_name:
        needs_quote = any(c in SPECIAL_CHARS_REQUIRE_QUOTE for c in col_name)
        if not needs_quote and col_name[0].isdigit():
            needs_quote = True
        if needs_quote:
            col_name = col_name.replace("'", "''")
            return f"{table_part}.'{col_name}'"

    return f"{table_part}.{col_name}"


# ---------------------------------------------------------------------------
# Property-ordering specs for the writer
# ---------------------------------------------------------------------------
#
# Each entry is (attribute_name, emit_style):
#   "property"        — emit  key: value   when value is truthy
#   "flag"            — emit  key           when value is truthy
#   "flag_false"      — emit  key: false    when value is explicitly False
#   "quoted_property" — emit  key: quote(v) when value is truthy

COLUMN_PROPERTY_ORDER: list[tuple[str, str]] = [
    (ColumnProp.DATA_TYPE, "property"),
    (ColumnProp.IS_HIDDEN, "flag"),
    (ColumnProp.IS_KEY, "flag"),
    (ColumnProp.IS_NULLABLE, "flag_false"),
    (ColumnProp.FORMAT_STRING, "property"),
    (ColumnProp.LINEAGE_TAG, "property"),
    (ColumnProp.SOURCE_LINEAGE_TAG, "property"),
    (ColumnProp.DATA_CATEGORY, "property"),
    (ColumnProp.SUMMARIZE_BY, "property"),
    (ColumnProp.IS_NAME_INFERRED, "flag"),
    (ColumnProp.SOURCE_COLUMN, "property"),
    (ColumnProp.SORT_BY_COLUMN, "quoted_property"),
    (ColumnProp.DISPLAY_FOLDER, "property"),
]

MEASURE_PROPERTY_ORDER: list[tuple[str, str]] = [
    (MeasureProp.FORMAT_STRING, "property"),
    (MeasureProp.DISPLAY_FOLDER, "property"),
    (MeasureProp.LINEAGE_TAG, "property"),
    (MeasureProp.SOURCE_LINEAGE_TAG, "property"),
    (MeasureProp.DATA_CATEGORY, "property"),
    (MeasureProp.IS_HIDDEN, "flag"),
]

TABLE_PROPERTY_ORDER: list[tuple[str, str]] = [
    (TableProp.SHOW_AS_VARIATIONS_ONLY, "flag"),
    (TableProp.LINEAGE_TAG, "property"),
    (TableProp.SOURCE_LINEAGE_TAG, "property"),
    (TableProp.IS_HIDDEN, "flag"),
    (TableProp.IS_PRIVATE, "flag"),
    (TableProp.EXCLUDE_FROM_MODEL_REFRESH, "flag"),
]
