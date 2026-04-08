"""TMDL grammar constants, structure registry, and shared operations.

Single source of truth for all TMDL grammar-level definitions:
- Token-level constants (keywords, flags, character sets)
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

# TMDL uses singular keyword names for repeated child entries.
# The Pydantic models use plural field names.
CHILDREN_NAMING_MAP: dict[str, str] = {
    "annotation": "annotations",
    "changedProperty": "changedProperties",
    "extendedProperty": "extendedProperties",
    "queryGroup": "queryGroups",
    "role": "roles",
    "tablePermission": "tablePermissions",
    "variation": "variations",
}

# Characters allowed in unquoted identifiers (beyond alphanumeric)
IDENTIFIER_CONTINUATION_CHARS = frozenset("_-/+.\\@?")

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
# 1a-iii. Expression serialisation style
# ---------------------------------------------------------------------------


class ExpressionStyle(str, Enum):
    """How an expression is serialised in TMDL.

    * ``INLINE``   : value follows ``=`` on the same declaration line.
    * ``MULTILINE``: value occupies indented lines below the ``=``.
    * ``BACKTICK`` : value is wrapped in triple-backtick delimiters.

    Writer policy
    -------------
    ``BACKTICK`` content is emitted at ``indent_level + 2`` tabs, closing
    delimiter at the same depth.  If the stored style is ``MULTILINE`` but
    the content *requires* backticks (trailing whitespace, comment lines,
    unbalanced quotes), the writer promotes the style to ``BACKTICK``
    automatically and logs a debug message.  This promotion only occurs for
    expressions created programmatically (e.g. from model.bim); expressions
    parsed from TMDL always carry the correct style.

    Indentation normalisation
    -------------------------
    On the first write, backtick content may shift from the original author's
    indentation depth to ``indent_level + 2``.  This is intentional
    normalisation.  Subsequent round-trips are stable.
    """

    INLINE = "inline"
    MULTILINE = "multiline"
    BACKTICK = "backtick"


class NameStyle(str, Enum):
    """Whether a TMDL object name was written with surrounding single-quotes.

    * ``UNQUOTED``: name was a bare identifier (e.g. ``column Price``).
    * ``QUOTED``  : name was single-quoted  (e.g. ``column 'My Col'``).

    The writer uses this to faithfully reproduce the original quoting style.
    It will still escalate to ``QUOTED`` when ``_requires_quoting`` detects
    characters that *require* quotes, regardless of the stored style.
    """

    QUOTED = "quoted"
    UNQUOTED = "unquoted"


def _requires_quoting(name: str) -> bool:
    """Return True if *name* contains characters that REQUIRE single-quoting.

    Digit-prefix names (e.g. ``97d97e``, ``14Q``) do *not* require quoting
    per the TMDL spec; the SDK writes them unquoted.  Only characters in
    ``SPECIAL_CHARS_REQUIRE_QUOTE`` mandate quotes.
    """
    return any(c in SPECIAL_CHARS_REQUIRE_QUOTE for c in name)


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
    "roles": "roles",
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
# 1d. Shared expression normalisation
# ---------------------------------------------------------------------------


def normalize_expression(
    raw: str | list[str] | None,
    preserve_trailing_blanks: bool = False,
) -> list[str]:
    """Normalize a raw TMDL expression to a list of lines with relative indentation.

    Strips the minimum common leading-tab count from every non-empty line so
    that expression text is stable across round-trips regardless of the
    absolute indentation in the source file.

    Handles the common case where the first line lost its leading tabs via
    ``.strip()`` (e.g. 0 tabs) while subsequent lines retain theirs.  In that
    situation the base indent is derived from lines 1+ so all lines are
    rebased consistently.

    Args:
        raw: Raw expression string or list of lines.
        preserve_trailing_blanks: When ``True`` (used for ``BACKTICK``
            expressions), trailing blank lines are retained verbatim because
            the spec says backtick content is read verbatim.  When ``False``
            (default, used for ``MULTILINE`` / ``INLINE``), trailing blank
            lines are stripped per the TMDL spec.

    Returns:
        A list of lines (possibly empty).  Never returns ``None``.
    """
    if raw is None:
        return []

    if isinstance(raw, list):
        raw_lines = list(raw)
    else:
        if not raw.strip():
            return []
        raw_lines = raw.split("\n")
        # Remove trailing empty lines (common artifact) but preserve
        # leading blank lines: they are part of the expression per
        # the TMDL spec ("vertical whitespace is part of expression").
        if not preserve_trailing_blanks:
            while raw_lines and not raw_lines[-1].strip():
                raw_lines.pop()

    if len(raw_lines) <= 1:
        # Single-line: strip leading/trailing whitespace (tabs from
        # source indentation) since there is no multi-line structure.
        return [raw_lines[0].strip()] if raw_lines and raw_lines[0].strip() else raw_lines

    # Filter to non-empty lines for computing minimum indent
    non_empty = [line for line in raw_lines if line.strip()]
    if not non_empty:
        return raw_lines

    # Count leading tabs on each non-empty line
    tab_counts = [len(line) - len(line.lstrip("\t")) for line in non_empty]
    min_tabs = min(tab_counts)

    # If the first non-empty line has 0 tabs but others have more,
    # it was likely stripped by .strip(): use the min from remaining
    # lines as the true base indent.
    if min_tabs == 0 and len(tab_counts) > 1:
        remaining = tab_counts[1:]
        if remaining and min(remaining) > 0:
            min_tabs = min(remaining)

    if min_tabs == 0:
        return raw_lines

    # Strip the common leading tabs
    prefix = "\t" * min_tabs
    result = []
    for line in raw_lines:
        if line[:min_tabs] == prefix:
            result.append(line[min_tabs:])
        else:
            result.append(line)
    return result


# ---------------------------------------------------------------------------
# Property-ordering specs for the writer
# ---------------------------------------------------------------------------
#
# Each entry is (attribute_name, emit_style):
#   "property"        : emit  key: value   when value is truthy
#   "flag"            : emit  key           when value is truthy
#   "flag_false"      : emit  key: false    when value is explicitly False
#   "quoted_property" : emit  key: quote(v) when value is truthy

COLUMN_PROPERTY_ORDER: list[tuple[str, str]] = [
    ("dataType", "property"),
    ("isHidden", "flag"),
    ("isKey", "flag"),
    ("isNullable", "flag_false"),
    ("alignment", "property"),
    ("formatString", "property"),
    ("sourceProviderType", "property"),
    ("lineageTag", "property"),
    ("sourceLineageTag", "property"),
    ("dataCategory", "property"),
    ("summarizeBy", "property"),
    ("isDataTypeInferred", "flag"),
    ("isNameInferred", "flag"),
    ("sourceColumn", "property"),
    ("sortByColumn", "quoted_property"),
    ("displayFolder", "property"),
]

MEASURE_PROPERTY_ORDER: list[tuple[str, str]] = [
    ("formatString", "property"),
    ("displayFolder", "property"),
    ("lineageTag", "property"),
    ("sourceLineageTag", "property"),
    ("dataCategory", "property"),
    ("isHidden", "flag"),
]

TABLE_PROPERTY_ORDER: list[tuple[str, str]] = [
    ("dataCategory", "property"),
    ("isHidden", "flag"),
    ("showAsVariationsOnly", "flag"),
    ("isPrivate", "flag"),
    ("excludeFromModelRefresh", "flag"),
    ("lineageTag", "property"),
    ("sourceLineageTag", "property"),
]
