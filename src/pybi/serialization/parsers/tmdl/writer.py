"""TMDL folder writer - serializes Pydantic models to TMDL files."""

import json
import logging
from pathlib import Path
from typing import Any

from pybi.serialization.parsers.tmdl.grammar import (
    BACKTICK_EXPR,
    COLUMN_PROPERTY_ORDER,
    DEFINITION_FILES,
    DEFINITION_FOLDERS,
    DESCRIPTION_PREFIX,
    MEASURE_PROPERTY_ORDER,
    TABLE_PROPERTY_ORDER,
    format_column_reference,
    quote_name,
    unquote_name,
)
from pybi.semanticmodel.definition import (
    Column,
    Culture,
    Expression,
    Measure,
    Model,
    Partition,
    Relationship,
    Table,
)

logger = logging.getLogger(__name__)


class TMDLWriter:
    """Serializes Pydantic models to TMDL text format."""

    def __init__(self):
        """Initialize the writer."""
        pass

    def _quote_name(self, name: str) -> str:
        """Quote a name if it contains special characters."""
        return quote_name(name)

    def _format_column_reference(self, ref: str) -> str:
        """Format a column reference with proper quoting."""
        return format_column_reference(ref)

    def _normalize_default_hierarchy_reference(self, value: Any) -> str | None:
        """Normalize variation.defaultHierarchy to a TMDL object reference string.

        model.bim commonly stores this as an object shape:
        {"table": "...", "hierarchy": "..."}
        while TMDL expects a named object reference like Table.'Hierarchy Name'.
        """
        if not value:
            return None

        if isinstance(value, str):
            return value

        if isinstance(value, dict):
            table = value.get("table")
            hierarchy = value.get("hierarchy")
            if table and hierarchy:
                return f"{table}.{hierarchy}"

        return str(value)

    def _write_properties_from_spec(
        self,
        model: Any,
        spec: list[tuple[str, str]],
        indent_level: int,
    ) -> list[str]:
        """Emit property lines according to a declarative ordering spec.

        Each spec entry is ``(attribute_name, emit_style)`` where *emit_style*
        is one of:

        * ``"property"``        : ``key: value``   when value is truthy
        * ``"flag"``            : ``key``           when value is truthy
        * ``"flag_false"``      : ``key: false``    when value is explicitly False
        * ``"quoted_property"`` : ``key: quote(v)`` when value is truthy
        """
        lines: list[str] = []
        indent = self._indent(indent_level)
        for attr, style in spec:
            key = attr
            value = getattr(model, attr, None)
            if style == "flag":
                if value:
                    lines.append(f"{indent}{key}")
            elif style == "flag_false":
                if value is False:
                    lines.append(f"{indent}{key}: false")
            elif style == "quoted_property":
                if value:
                    lines.append(f"{indent}{key}: {self._quote_name(value)}")
            else:  # "property"
                if value:
                    lines.append(f"{indent}{key}: {value}")
        return lines

    def _indent(self, level: int) -> str:
        """Get indentation string for a given level.

        Args:
            level: The indentation level (0 = no indent).

        Returns:
            Tab characters for the indentation level.
        """
        return "\t" * level

    def _normalize_expression_lines(
        self, expression: str | list[str] | None
    ) -> list[str]:
        """Convert an expression to a list of lines with normalized indentation.

        Strips the minimum common leading whitespace from all non-empty lines
        so the writer can re-indent them at the correct level.

        Handles the common case where ``transform_measure`` calls ``.strip()``
        on the raw expression string: the first line loses its leading tabs
        while subsequent lines retain theirs.  In that situation the base
        indent is derived from lines 1+ so all lines are rebased consistently.
        """
        if expression is None:
            return []

        if isinstance(expression, list):
            raw_lines = expression
        else:
            raw_lines = expression.split("\n") if "\n" in expression else [expression]

        # Filter to non-empty lines for computing minimum indent
        non_empty = [line for line in raw_lines if line.strip()]
        if not non_empty:
            return raw_lines

        # Count leading tabs on each non-empty line
        tab_counts = [len(line) - len(line.lstrip("\t")) for line in non_empty]
        min_tabs = min(tab_counts)

        # If the first non-empty line has 0 tabs but others have more,
        # it was likely stripped by .strip() : use the min from remaining
        # lines as the true base indent.
        if min_tabs == 0 and len(tab_counts) > 1:
            remaining = [c for i, c in enumerate(tab_counts) if i > 0]
            if remaining and min(remaining) > 0:
                min_tabs = min(remaining)

        if min_tabs == 0:
            return raw_lines

        # Strip the common leading tabs
        result = []
        for line in raw_lines:
            if line[:min_tabs] == "\t" * min_tabs:
                result.append(line[min_tabs:])
            else:
                result.append(line)
        return result

    def _format_expression(
        self, expression: str | list[str] | None, indent_level: int = 2
    ) -> str:
        """Format an expression for TMDL output.

        Args:
            expression: The expression (string or list of lines).
            indent_level: The indentation level for multi-line expressions.

        Returns:
            Formatted expression string.
        """
        if expression is None:
            return ""

        if isinstance(expression, list):
            lines = expression
        else:
            lines = expression.split("\n") if "\n" in expression else [expression]

        if len(lines) == 1:
            return lines[0]

        # Multi-line: indent each line
        indent = self._indent(indent_level)
        return "\n".join(f"{indent}{line}" for line in lines)

    def _needs_backticks(self, expression: str | list[str] | None) -> bool:
        """Check if an expression needs triple-backtick enclosure.

        Backticks are needed when the expression body would be altered by
        normal TMDL tokenization : specifically when lines contain:
        * trailing whitespace (spaces or tabs)
        * leading spaces (after stripping leading tabs) that convey
          indentation which the tokenizer would discard
        * single quotes (') that the lexer would misinterpret as
          TMDL quoted-name delimiters

        Args:
            expression: The expression to check.

        Returns:
            True if backticks are needed.
        """
        if expression is None:
            return False

        if isinstance(expression, list):
            text = "\n".join(expression)
        else:
            text = expression

        for line in text.split("\n"):
            # Trailing whitespace
            if line.endswith(" ") or line.endswith("\t"):
                return True
            # Leading spaces (after tabs) : would be lost by tokenizer
            stripped_tabs = line.lstrip("\t")
            if stripped_tabs and stripped_tabs[0] == " ":
                return True
            # Single quotes : lexer interprets as quoted-name delimiters
            if "'" in line:
                return True
            # Double-quoted strings : _smart_join_expression in the parser
            # adds spaces around adjacent tokens (e.g. "x"&y -> "x" & y)
            if '"' in line:
                return True

        return False

    def _write_annotation(self, annotation: dict[str, Any], indent_level: int) -> str:
        """Write an annotation.

        Args:
            annotation: Annotation dict with 'name' and 'value' keys.
            indent_level: The indentation level.

        Returns:
            TMDL annotation line.
        """
        indent = self._indent(indent_level)
        name = annotation.get("name", "")
        # Annotations may store their value under "value" (Annotation model)
        # or "expression" (from expand_node when reading TMDL)
        value = annotation.get("value") or annotation.get("expression", "")

        # Format value - if it looks like JSON, keep it as-is
        if isinstance(value, (dict, list)):
            value = json.dumps(value)

        return f"{indent}annotation {name} = {value}"

    def _write_property(self, key: str, value: Any, indent_level: int) -> str | None:
        """Write a property line.

        Args:
            key: Property name.
            value: Property value.
            indent_level: The indentation level.

        Returns:
            TMDL property line, or None if value is None/empty.
        """
        if value is None:
            return None

        indent = self._indent(indent_level)

        # Handle boolean - can be shorthand for True
        if isinstance(value, bool):
            if value:
                return f"{indent}{key}"
            else:
                return f"{indent}{key}: false"

        # Handle numbers
        if isinstance(value, (int, float)):
            return f"{indent}{key}: {value}"

        # Handle strings - quote if contains special characters
        str_value = str(value)
        # Quote if contains semicolons, spaces, or other special chars
        needs_quote = any(c in str_value for c in [";", " ", "\n", "\t", "\r"])
        if needs_quote and not (str_value.startswith('"') and str_value.endswith('"')):
            # Escape any internal quotes
            str_value = str_value.replace('"', '\\"')
            return f'{indent}{key}: "{str_value}"'

        return f"{indent}{key}: {value}"

    def write_database(self, compatibility_level: int) -> str:
        """Write database.tmdl content.

        Args:
            compatibility_level: The model's compatibility level.

        Returns:
            TMDL database file content.
        """
        lines = [
            "database",
            f"\tcompatibilityLevel: {compatibility_level}",
            "",
            "",  # Extra trailing newline to match original format
        ]
        return "\n".join(lines)

    def write_column(self, column: Column, indent_level: int = 1) -> list[str]:
        """Write a column definition.

        Args:
            column: The Column model.
            indent_level: Base indentation level.

        Returns:
            List of TMDL lines for the column.
        """
        lines: list[str] = []
        indent = self._indent(indent_level)
        prop_indent = indent_level + 1

        # Column declaration (with expression for calculated columns)
        if column.expression:
            expr_lines = self._normalize_expression_lines(column.expression)
            is_multiline = len(expr_lines) > 1

            # Check if expression needs triple backticks (for trailing whitespace)
            needs_backticks = self._needs_backticks(column.expression)

            if needs_backticks:
                # Use triple backtick syntax for expressions with trailing whitespace
                lines.append(
                    f"{indent}column {self._quote_name(column.name)} = {BACKTICK_EXPR}"
                )
                expr_indent = self._indent(
                    indent_level + 2
                )  # 2 levels for backtick content
                for expr_line in expr_lines:
                    lines.append(f"{expr_indent}{expr_line}")
                lines.append(f"{expr_indent}{BACKTICK_EXPR}")
            elif is_multiline:
                lines.append(f"{indent}column {self._quote_name(column.name)} =")
                expr_indent = self._indent(indent_level + 2)
                for expr_line in expr_lines:
                    lines.append(f"{expr_indent}{expr_line}")
            else:
                expr_text = expr_lines[0].strip() if expr_lines else ""
                lines.append(
                    f"{indent}column {self._quote_name(column.name)} = {expr_text}"
                )
        else:
            lines.append(f"{indent}column {self._quote_name(column.name)}")

        # Properties (order matches typical TMDL output from Power BI)
        lines.extend(
            self._write_properties_from_spec(column, COLUMN_PROPERTY_ORDER, prop_indent)
        )

        # Variations (with empty line before)
        if column.variations:
            lines.append("")  # Empty line before variations
            for variation in column.variations:
                var_indent = prop_indent
                var_prop_indent = var_indent + 1
                lines.append(
                    f"{self._indent(var_indent)}variation {variation.name or ''}"
                )
                if variation.isDefault:
                    lines.append(f"{self._indent(var_prop_indent)}isDefault")
                if variation.relationship:
                    lines.append(
                        f"{self._indent(var_prop_indent)}relationship: {variation.relationship}"
                    )
                if variation.defaultHierarchy:
                    hierarchy_value = self._normalize_default_hierarchy_reference(
                        variation.defaultHierarchy
                    )
                    if hierarchy_value is None:
                        continue
                    hierarchy_ref = self._format_column_reference(hierarchy_value)
                    lines.append(
                        f"{self._indent(var_prop_indent)}defaultHierarchy: {hierarchy_ref}"
                    )

        # Changed properties (with empty line before)
        if column.changedProperties:
            lines.append("")  # Empty line before changedProperties
            for changed in column.changedProperties:
                if isinstance(changed, dict) and "property" in changed:
                    lines.append(
                        f"{self._indent(prop_indent)}changedProperty = {changed['property']}"
                    )
                elif isinstance(changed, str):
                    lines.append(
                        f"{self._indent(prop_indent)}changedProperty = {changed}"
                    )

        # Annotations (with empty line before first and between each)
        if column.annotations:
            lines.append("")  # Empty line before annotations
            for i, ann in enumerate(column.annotations):
                lines.append(self._write_annotation(ann, prop_indent))
                if i < len(column.annotations) - 1:
                    lines.append("")  # Empty line between annotations

        # relatedColumnDetails (anonymous child block)
        if column.relatedColumnDetails:
            lines.append(f"{self._indent(prop_indent)}relatedColumnDetails")
            rcd = column.relatedColumnDetails
            if isinstance(rcd, str):
                for rcd_line in rcd.strip().split("\n"):
                    lines.append(f"{self._indent(prop_indent + 1)}{rcd_line.strip()}")
            elif isinstance(rcd, dict):
                for k, v in rcd.items():
                    lines.append(f"{self._indent(prop_indent + 1)}{k}: {v}")

        # Extended properties
        if column.extendedProperties:
            lines.append("")
            for ep in column.extendedProperties:
                ep_name = ep.get("name") or ""
                ep_expr = ep.get("expression", "")
                ep_lines = self._normalize_expression_lines(ep_expr) if ep_expr else []
                needs_bt = bool(ep_lines) and self._needs_backticks(ep_lines)
                if needs_bt:
                    lines.append(
                        f"{self._indent(prop_indent)}extendedProperty {ep_name} = {BACKTICK_EXPR}"
                    )
                    for el in ep_lines:
                        lines.append(f"{self._indent(prop_indent + 2)}{el}")
                    lines.append(f"{self._indent(prop_indent + 2)}{BACKTICK_EXPR}")
                else:
                    lines.append(
                        f"{self._indent(prop_indent)}extendedProperty {ep_name} ="
                    )
                    for el in ep_lines:
                        lines.append(f"{self._indent(prop_indent + 2)}{el}")

        return lines

    def write_measure(self, measure: Measure, indent_level: int = 1) -> list[str]:
        """Write a measure definition.

        Args:
            measure: The Measure model.
            indent_level: Base indentation level.

        Returns:
            List of TMDL lines for the measure.
        """
        lines: list[str] = []
        indent = self._indent(indent_level)
        prop_indent = indent_level + 1

        # Measure declaration with expression
        expr_lines = self._normalize_expression_lines(measure.expression)
        is_multiline = len(expr_lines) > 1
        needs_backticks = is_multiline and self._needs_backticks(expr_lines)

        if needs_backticks:
            lines.append(
                f"{indent}measure {self._quote_name(measure.name)} = {BACKTICK_EXPR}"
            )
            expr_indent = self._indent(indent_level + 2)
            for expr_line in expr_lines:
                lines.append(f"{expr_indent}{expr_line}")
            lines.append(f"{expr_indent}{BACKTICK_EXPR}")
        elif is_multiline:
            lines.append(f"{indent}measure {self._quote_name(measure.name)} =")
            expr_indent = self._indent(indent_level + 2)
            for expr_line in expr_lines:
                lines.append(f"{expr_indent}{expr_line}")
        else:
            # Handle empty or missing expression
            expr_text = (expr_lines[0] if expr_lines else "").strip()
            if expr_text:
                lines.append(
                    f"{indent}measure {self._quote_name(measure.name)} = {expr_text}"
                )
            else:
                # No `=` for empty expression : avoids parser capturing
                # subsequent properties as a multi-line expression body
                lines.append(f"{indent}measure {self._quote_name(measure.name)}")

        # Properties
        lines.extend(
            self._write_properties_from_spec(
                measure, MEASURE_PROPERTY_ORDER, prop_indent
            )
        )

        # Description (as /// prefix)
        if measure.description:
            # Description goes BEFORE the measure declaration
            # We need to handle this differently - insert at beginning
            desc_lines = measure.description.split("\n")
            desc_prefix = [
                f"{indent}{DESCRIPTION_PREFIX} {line}" for line in desc_lines
            ]
            lines = desc_prefix + lines

        # Format string definition (with empty line before)
        if measure.formatStringDefinition:
            expr = measure.formatStringDefinition.get("expression", "")
            if expr:
                lines.append("")  # Empty line before formatStringDefinition
                lines.append(
                    f"{self._indent(prop_indent)}formatStringDefinition = {expr}"
                )

        # Annotations (with empty line before first annotation)
        if measure.annotations:
            lines.append("")  # Empty line before annotations
            for ann in measure.annotations:
                lines.append(self._write_annotation(ann, prop_indent))

        # Changed properties (with empty line before)
        if measure.changedProperties:
            lines.append("")  # Empty line before changedProperties
            for changed in measure.changedProperties:
                if isinstance(changed, dict) and "property" in changed:
                    lines.append(
                        f"{self._indent(prop_indent)}changedProperty = {changed['property']}"
                    )
                elif isinstance(changed, str):
                    lines.append(
                        f"{self._indent(prop_indent)}changedProperty = {changed}"
                    )

        # Extended properties
        if measure.extendedProperties:
            lines.append("")
            for ep in measure.extendedProperties:
                ep_name = ep.get("name") or ""
                ep_expr = ep.get("expression", "")
                ep_lines = self._normalize_expression_lines(ep_expr) if ep_expr else []
                needs_bt = bool(ep_lines) and self._needs_backticks(ep_lines)
                if needs_bt:
                    lines.append(
                        f"{self._indent(prop_indent)}extendedProperty {ep_name} = {BACKTICK_EXPR}"
                    )
                    for el in ep_lines:
                        lines.append(f"{self._indent(prop_indent + 2)}{el}")
                    lines.append(f"{self._indent(prop_indent + 2)}{BACKTICK_EXPR}")
                else:
                    lines.append(
                        f"{self._indent(prop_indent)}extendedProperty {ep_name} ="
                    )
                    for el in ep_lines:
                        lines.append(f"{self._indent(prop_indent + 2)}{el}")

        return lines

    def write_partition(self, partition: Partition, indent_level: int = 1) -> list[str]:
        """Write a partition definition.

        Args:
            partition: The Partition model.
            indent_level: Base indentation level.

        Returns:
            List of TMDL lines for the partition.
        """
        lines: list[str] = []
        indent = self._indent(indent_level)
        prop_indent = indent_level + 1

        # Partition declaration with source type
        source_type = partition.source.type
        lines.append(
            f"{indent}partition {self._quote_name(partition.name)} = {source_type}"
        )

        # Mode
        if partition.mode:
            lines.append(f"{self._indent(prop_indent)}mode: {partition.mode}")

        # Query group
        if partition.queryGroup:
            lines.append(
                f"{self._indent(prop_indent)}queryGroup: {partition.queryGroup}"
            )

        # Source - format depends on source type
        source = partition.source

        # Entity source with nested properties
        if source.entityName or source.expressionSource:
            lines.append(f"{self._indent(prop_indent)}source")
            source_prop_indent = prop_indent + 1
            if source.entityName:
                lines.append(
                    f"{self._indent(source_prop_indent)}entityName: {source.entityName}"
                )
            if source.expressionSource:
                lines.append(
                    f"{self._indent(source_prop_indent)}expressionSource: {self._quote_name(source.expressionSource)}"
                )
        # M expression source - use inline "source =" format
        elif source.expression:
            expr_lines = self._normalize_expression_lines(source.expression)
            is_multiline = len(expr_lines) > 1
            needs_backticks = is_multiline and self._needs_backticks(expr_lines)

            if needs_backticks:
                lines.append(f"{self._indent(prop_indent)}source = {BACKTICK_EXPR}")
                expr_indent = self._indent(prop_indent + 2)
                for expr_line in expr_lines:
                    lines.append(f"{expr_indent}{expr_line}")
                lines.append(f"{expr_indent}{BACKTICK_EXPR}")
            elif is_multiline:
                lines.append(f"{self._indent(prop_indent)}source =")
                expr_indent = self._indent(prop_indent + 1)
                for expr_line in expr_lines:
                    lines.append(f"{expr_indent}{expr_line}")
            else:
                expr_text = (expr_lines[0] if expr_lines else "").strip()
                if expr_text:
                    lines.append(f"{self._indent(prop_indent)}source = {expr_text}")
                else:
                    lines.append(f"{self._indent(prop_indent)}source =")

        return lines

    def write_table(self, table: Table) -> str:
        """Write a complete table.tmdl file content.

        Args:
            table: The Table model.

        Returns:
            Complete TMDL table file content.
        """
        lines: list[str] = []

        # Description
        if table.description:
            for desc_line in table.description.split("\n"):
                lines.append(f"{DESCRIPTION_PREFIX} {desc_line}")

        # Table declaration
        lines.append(f"table {self._quote_name(table.name)}")

        # Properties (order matches typical TMDL output from Power BI)
        lines.extend(self._write_properties_from_spec(table, TABLE_PROPERTY_ORDER, 1))

        # Measures first (common TMDL pattern)
        if table.measures:
            lines.append("")  # Blank line before measures
            for measure in table.measures:
                lines.extend(self.write_measure(measure, indent_level=1))
                lines.append("")  # Blank line between measures

        # Columns
        if table.columns:
            if not table.measures:
                lines.append("")  # Blank line before columns if no measures
            for column in table.columns:
                lines.extend(self.write_column(column, indent_level=1))
                lines.append("")  # Blank line between columns

        # Hierarchies (before partitions in typical TMDL files)
        if table.hierarchies:
            for hierarchy in table.hierarchies:
                lines.extend(self._write_hierarchy(hierarchy, indent_level=1))
                # Note: hierarchy already ends with empty line after last level

        # Partitions
        if table.partitions:
            for partition in table.partitions:
                lines.extend(self.write_partition(partition, indent_level=1))
                lines.append("")  # Blank line between partitions

        # Annotations
        if table.annotations:
            lines.append("")  # Blank line before annotations
            for ann in table.annotations:
                lines.append(self._write_annotation(ann, 1))

        # Changed properties
        if table.changedProperties:
            lines.append("")
            for changed in table.changedProperties:
                if isinstance(changed, dict) and "property" in changed:
                    lines.append(f"\tchangedProperty = {changed['property']}")
                elif isinstance(changed, str):
                    lines.append(f"\tchangedProperty = {changed}")

        # Calculation group (bare keyword when empty, else with properties)
        if table.calculationGroup is not None:
            cg_list = (
                table.calculationGroup
                if isinstance(table.calculationGroup, list)
                else [table.calculationGroup]
            )
            for cg in cg_list:
                lines.append("")
                lines.append("\tcalculationGroup")
                if isinstance(cg, dict):
                    for k, v in cg.items():
                        if k != "name" and v is not None:
                            lines.append(f"\t\t{k}: {v}")

        lines.append("")  # Final newline
        return "\n".join(lines)

    def _write_hierarchy(
        self, hierarchy: dict[str, Any], indent_level: int
    ) -> list[str]:
        """Write a hierarchy definition.

        Args:
            hierarchy: The hierarchy dict.
            indent_level: Base indentation level.

        Returns:
            List of TMDL lines for the hierarchy.
        """
        lines: list[str] = []
        indent = self._indent(indent_level)
        prop_indent = indent_level + 1

        name = hierarchy.get("name", "")
        lines.append(f"{indent}hierarchy {self._quote_name(name)}")

        if hierarchy.get("lineageTag"):
            lines.append(
                f"{self._indent(prop_indent)}lineageTag: {hierarchy['lineageTag']}"
            )

        if hierarchy.get("sourceLineageTag"):
            lines.append(
                f"{self._indent(prop_indent)}sourceLineageTag: {hierarchy['sourceLineageTag']}"
            )

        # Levels : transformer stores under "level" (singular, not in CHILDREN_NAMING_MAP)
        # but model.bim uses "levels" (plural), so accept both keys.
        levels = hierarchy.get("levels") or hierarchy.get("level") or []
        if levels:
            lines.append("")  # Empty line before levels

        for level in levels:
            level_name = level.get("name", "")
            lines.append(
                f"{self._indent(prop_indent)}level {self._quote_name(level_name)}"
            )

            level_prop_indent = prop_indent + 1
            if level.get("lineageTag"):
                lines.append(
                    f"{self._indent(level_prop_indent)}lineageTag: {level['lineageTag']}"
                )
            if level.get("sourceLineageTag"):
                lines.append(
                    f"{self._indent(level_prop_indent)}sourceLineageTag: {level['sourceLineageTag']}"
                )
            if level.get("column"):
                col_val = unquote_name(level["column"]) or level["column"]
                lines.append(
                    f"{self._indent(level_prop_indent)}column: {self._quote_name(col_val)}"
                )
            if level.get("ordinal") is not None:
                lines.append(
                    f"{self._indent(level_prop_indent)}ordinal: {level['ordinal']}"
                )
            # Level annotations
            if level.get("annotations"):
                lines.append("")
                for ann in level["annotations"]:
                    lines.append(self._write_annotation(ann, level_prop_indent))
            lines.append("")  # Empty line after each level

        # Hierarchy annotations
        if hierarchy.get("annotations"):
            lines.append("")
            for ann in hierarchy["annotations"]:
                lines.append(self._write_annotation(ann, prop_indent))

        return lines

    def write_relationship(self, relationship: Relationship) -> list[str]:
        """Write a relationship definition.

        Args:
            relationship: The Relationship model.

        Returns:
            List of TMDL lines for the relationship.
        """
        lines: list[str] = []

        # Relationship declaration
        name_part = f" {relationship.name}" if relationship.name else ""
        lines.append(f"relationship{name_part}")

        # isActive (only if false, since true is default)
        if relationship.isActive is False:
            lines.append(f"\tisActive: false")

        # Cardinality
        if relationship.toCardinality:
            lines.append(f"\ttoCardinality: {relationship.toCardinality}")

        if relationship.fromCardinality:
            lines.append(f"\tfromCardinality: {relationship.fromCardinality}")

        # Cross filtering
        if relationship.crossFilteringBehavior:
            lines.append(
                f"\tcrossFilteringBehavior: {relationship.crossFilteringBehavior}"
            )

        # From/To columns (formatted as Table.Column or 'Table Name'.'Column Name')
        from_table = self._quote_name(relationship.fromTable)
        from_col = self._quote_name(relationship.fromColumn)
        to_table = self._quote_name(relationship.toTable)
        to_col = self._quote_name(relationship.toColumn)

        lines.append(f"\tfromColumn: {from_table}.{from_col}")
        lines.append(f"\ttoColumn: {to_table}.{to_col}")

        # Other properties
        if relationship.securityFilteringBehavior:
            lines.append(
                f"\tsecurityFilteringBehavior: {relationship.securityFilteringBehavior}"
            )

        if relationship.joinOnDateBehavior:
            lines.append(f"\tjoinOnDateBehavior: {relationship.joinOnDateBehavior}")

        # Annotations
        if relationship.annotations:
            for ann in relationship.annotations:
                lines.append(self._write_annotation(ann, 1))

        return lines

    def write_relationships(self, relationships: list[Relationship] | None) -> str:
        """Write relationships.tmdl content.

        Args:
            relationships: List of Relationship models.

        Returns:
            Complete TMDL relationships file content.
        """
        if not relationships:
            return ""

        lines: list[str] = []
        for rel in relationships:
            lines.extend(self.write_relationship(rel))
            lines.append("")  # Blank line between relationships

        lines.append("")  # Trailing newline to match original format
        return "\n".join(lines)

    def write_expression(self, expression: Expression) -> list[str]:
        """Write an expression definition.

        Args:
            expression: The Expression model.

        Returns:
            List of TMDL lines for the expression.
        """
        lines: list[str] = []

        # Description
        if expression.description:
            for desc_line in expression.description.split("\n"):
                lines.append(f"{DESCRIPTION_PREFIX} {desc_line}")

        # Expression declaration with expression body
        expr_lines = self._normalize_expression_lines(expression.expression)

        is_multiline = len(expr_lines) > 1
        needs_backticks = is_multiline and self._needs_backticks(expr_lines)

        if needs_backticks:
            lines.append(
                f"expression {self._quote_name(expression.name)} = {BACKTICK_EXPR}"
            )
            for expr_line in expr_lines:
                lines.append(f"\t\t{expr_line}")
            lines.append(f"\t\t{BACKTICK_EXPR}")
        elif is_multiline:
            lines.append(f"expression {self._quote_name(expression.name)} =")
            for expr_line in expr_lines:
                lines.append(f"\t\t{expr_line}")
        elif expr_lines:
            lines.append(
                f"expression {self._quote_name(expression.name)} = {expr_lines[0]}"
            )
        else:
            # Empty expression
            lines.append(f"expression {self._quote_name(expression.name)} =")

        # Properties
        if expression.lineageTag:
            lines.append(f"\tlineageTag: {expression.lineageTag}")

        if expression.sourceLineageTag:
            lines.append(f"\tsourceLineageTag: {expression.sourceLineageTag}")

        if expression.queryGroup:
            lines.append(f"\tqueryGroup: {expression.queryGroup}")

        if expression.kind:
            lines.append(f"\tkind: {expression.kind}")

        if expression.mAttributes:
            lines.append(f"\tmAttributes: {expression.mAttributes}")

        # Annotations (with empty line before)
        if expression.annotations:
            lines.append("")  # Empty line before annotations
            for ann in expression.annotations:
                lines.append(self._write_annotation(ann, 1))

        return lines

    def write_expressions(self, expressions: list[Expression] | None) -> str:
        """Write expressions.tmdl content.

        Args:
            expressions: List of Expression models.

        Returns:
            Complete TMDL expressions file content.
        """
        if not expressions:
            return ""

        lines: list[str] = []
        for expr in expressions:
            lines.extend(self.write_expression(expr))
            lines.append("")  # Blank line between expressions

        lines.append("")  # Trailing newline to match original format
        return "\n".join(lines)

    def write_culture(self, culture: Culture) -> str:
        """Write a culture.tmdl file content.

        Args:
            culture: The Culture model.

        Returns:
            Complete TMDL culture file content.
        """
        lines: list[str] = []

        # CultureInfo declaration
        lines.append(f"cultureInfo {culture.name}")

        # Linguistic metadata
        if culture.linguisticMetadata:
            content = culture.linguisticMetadata.get("content")
            content_type = culture.linguisticMetadata.get("contentType", "json")

            if content:
                lines.append("")  # Blank line
                lines.append("\tlinguisticMetadata =")

                # If content is a string (pre-formatted YAML-like), write it as-is
                if isinstance(content, str):
                    # Split by lines and preserve formatting
                    for content_line in content.split("\n"):
                        # Add base indentation if line doesn't start with it
                        if content_line.strip():
                            lines.append(f"\t\t{content_line}")
                        else:
                            lines.append("")
                # If content is a dict, format as JSON
                elif isinstance(content, dict):
                    json_str = json.dumps(content, indent=2)
                    for json_line in json_str.split("\n"):
                        lines.append(f"\t\t\t{json_line}")
                else:
                    lines.append(f"\t\t\t{content}")

                # contentType property
                if content_type:
                    lines.append(f"\t\tcontentType: {content_type}")

        lines.append("")  # Final newline
        lines.append("")  # Extra trailing newline to match original format
        return "\n".join(lines)

    def write_model(self, model: Model, tables: list[Table] | None = None) -> str:
        """Write model.tmdl content.

        Args:
            model: The Model object.
            tables: Optional list of tables to generate refs for.

        Returns:
            Complete TMDL model file content.
        """
        lines: list[str] = []

        # Model declaration
        lines.append("model Model")

        # Properties
        if model.culture:
            lines.append(f"\tculture: {model.culture}")

        if model.defaultPowerBIDataSourceVersion:
            lines.append(
                f"\tdefaultPowerBIDataSourceVersion: {model.defaultPowerBIDataSourceVersion}"
            )

        if model.sourceQueryCulture:
            lines.append(f"\tsourceQueryCulture: {model.sourceQueryCulture}")

        if model.discourageImplicitMeasures:
            lines.append(f"\tdiscourageImplicitMeasures")

        if model.maxParallelismPerRefresh is not None:
            lines.append(
                f"\tmaxParallelismPerRefresh: {model.maxParallelismPerRefresh}"
            )

        # Data access options
        if model.dataAccessOptions:
            lines.append("\tdataAccessOptions")
            for key, value in model.dataAccessOptions.items():
                if value is True:
                    lines.append(f"\t\t{key}")
                elif value is not None and value is not False:
                    lines.append(f"\t\t{key}: {value}")

        # Annotations (with empty line after each)
        if model.annotations:
            lines.append("")  # Blank line before annotations
            for ann in model.annotations:
                lines.append(self._write_annotation(ann, 0))
                lines.append("")  # Empty line after each annotation

        # Table refs
        tables_to_ref = tables or model.tables
        if tables_to_ref:
            lines.append("")  # Blank line before refs
            for table in tables_to_ref:
                lines.append(f"ref table {self._quote_name(table.name)}")

        # Culture refs
        if model.cultures:
            lines.append("")  # Blank line before culture refs
            for culture in model.cultures:
                lines.append(f"ref cultureInfo {culture.name}")

        lines.append("")  # Final newline
        return "\n".join(lines)


# ------------------------------------------
# In-memory writer (produces dict[str, str] instead of writing to disk)
# ------------------------------------------


class TMDLPartsWriter:
    """Produce TMDL content as a ``dict[str, str]`` (path → text).

    Paths are relative to the ``definition/`` folder and use forward slashes,
    e.g. ``"database.tmdl"``, ``"tables/Sales.tmdl"``.

    All non-empty files that ``TMDLFolderWriter`` would write are included.
    """

    def __init__(self) -> None:
        self.writer = TMDLWriter()

    def _sanitize_filename(self, name: str) -> str:
        invalid_chars = '<>:"/\\|?*'
        result = name
        for char in invalid_chars:
            result = result.replace(char, "_")
        return result

    def write(self, semantic_model: Any) -> dict[str, str]:
        """Return ``{relative_path: tmdl_text}`` for every TMDL file.

        Args:
            semantic_model: A ``SemanticModelDefinition`` (must have
                ``.compatibilityLevel`` and ``.model``).
        """
        files: dict[str, str] = {}

        compat_level = getattr(semantic_model, "compatibilityLevel", 1600)
        db_content = self.writer.write_database(compat_level)
        if db_content.strip():
            files[DEFINITION_FILES["database"]] = db_content

        model = semantic_model.model

        model_content = self.writer.write_model(model, model.tables)
        if model_content.strip():
            files[DEFINITION_FILES["model"]] = model_content

        rel_content = self.writer.write_relationships(model.relationships)
        if rel_content.strip():
            files[DEFINITION_FILES["relationships"]] = rel_content

        expr_content = self.writer.write_expressions(model.expressions)
        if expr_content.strip():
            files[DEFINITION_FILES["expressions"]] = expr_content

        if model.cultures:
            for culture in model.cultures:
                content = self.writer.write_culture(culture)
                if content.strip():
                    files[f"{DEFINITION_FOLDERS['cultures']}/{culture.name}.tmdl"] = (
                        content
                    )

        if model.tables:
            for table in model.tables:
                content = self.writer.write_table(table)
                if content.strip():
                    fname = f"{self._sanitize_filename(table.name)}.tmdl"
                    files[f"{DEFINITION_FOLDERS['tables']}/{fname}"] = content

        return files
