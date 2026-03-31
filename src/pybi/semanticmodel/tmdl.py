"""TMDL (Tabular Model Definition Language) parser."""

from __future__ import annotations

import re

from . import Column, Measure, SemanticModel, Table

_PROPERTY_RE = re.compile(r"^([\w][\w\s]*):\s*(.*)$")
_MEASURE_DEF_RE = re.compile(r"^measure\s+(.+?)\s*=\s*(.+)$")


def _get_indent_level(line: str) -> int:
    """Return the indentation level of a line (0-based, 4-space indents)."""
    stripped = line.lstrip()
    if not stripped:
        return -1
    return (len(line) - len(stripped)) // 4


def _strip_quotes(value: str) -> str:
    """Remove surrounding single quotes from a value if present."""
    value = value.strip()
    if len(value) >= 2 and value[0] == "'" and value[-1] == "'":
        return value[1:-1]
    return value


def parse_tmdl(content: str) -> SemanticModel:
    """Parse TMDL text content into a SemanticModel.

    Args:
        content: The TMDL document as a string.

    Returns:
        A SemanticModel populated from the parsed TMDL.
    """
    model = SemanticModel(name="Model")
    current_table: Table | None = None
    current_col: Column | None = None
    current_measure: Measure | None = None

    for line in content.splitlines():
        stripped = line.strip()

        # Skip empty lines and doc comments
        if not stripped or stripped.startswith("///"):
            continue

        level = _get_indent_level(line)

        if level == 0:
            if stripped.startswith("model "):
                model.name = stripped[6:].strip()
            elif stripped.startswith("table "):
                current_table = Table(name=stripped[6:].strip())
                model.tables.append(current_table)
                current_col = None
                current_measure = None

        elif level == 1:
            if current_table is None:
                # Model-level property (e.g. "culture: en-US")
                prop_m = _PROPERTY_RE.match(stripped)
                if prop_m:
                    key = prop_m.group(1).strip()
                    value = prop_m.group(2).strip()
                    if key == "culture":
                        model.culture = value
                continue

            current_col = None
            current_measure = None

            measure_m = _MEASURE_DEF_RE.match(stripped)
            if measure_m:
                name = _strip_quotes(measure_m.group(1))
                expr = measure_m.group(2).strip()
                current_measure = Measure(name=name, expression=expr)
                current_table.measures.append(current_measure)
            elif stripped.startswith("column "):
                col_name = _strip_quotes(stripped[7:].strip())
                current_col = Column(name=col_name)
                current_table.columns.append(current_col)
            elif stripped == "isHidden":
                current_table.is_hidden = True

        elif level == 2:
            prop_m = _PROPERTY_RE.match(stripped)
            if prop_m:
                key = prop_m.group(1).strip()
                value = prop_m.group(2).strip()
                if current_col is not None:
                    if key == "dataType":
                        current_col.data_type = value
                    elif key == "formatString":
                        current_col.format_string = value
                    elif key == "summarizeBy":
                        current_col.summarize_by = value
                elif current_measure is not None:
                    if key == "displayFolder":
                        current_measure.display_folder = value
                    elif key == "formatString":
                        current_measure.format_string = value
            elif stripped == "isKey" and current_col is not None:
                current_col.is_key = True

    return model
