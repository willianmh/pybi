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
    normalize_expression,
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

        Delegates to :func:`grammar.normalize_expression`.
        """
        return normalize_expression(expression)

    def _write_expr_block(
        self,
        decl: str,
        expression: str | list[str] | None,
        indent_level: int,
    ) -> list[str]:
        """Write an expression declaration with its body.

        Handles normalize → backtick check → backtick or multi-line or
        single-line form.  Content is emitted at *indent_level + 2*,
        closing backtick at *indent_level + 1* (per TMDL spec, it
        determines the left boundary and should be shallower than
        content).

        Args:
            decl: Declaration prefix without trailing ``=``, e.g.
                ``"\\tmeasure 'Sales Amount'"``.
            expression: The expression value.
            indent_level: The indentation level of the declaration line.

        Returns:
            List of TMDL lines.
        """
        lines: list[str] = []
        expr_lines = self._normalize_expression_lines(expression)
        is_multiline = len(expr_lines) > 1
        needs_backticks = is_multiline and self._needs_backticks(expr_lines)

        if needs_backticks:
            lines.append(f"{decl} = {BACKTICK_EXPR}")
            expr_indent = self._indent(indent_level + 2)
            for expr_line in expr_lines:
                if expr_line:
                    lines.append(f"{expr_indent}{expr_line}")
                else:
                    lines.append("")
            lines.append(f"{self._indent(indent_level + 1)}{BACKTICK_EXPR}")
        elif is_multiline:
            lines.append(f"{decl} =")
            expr_indent = self._indent(indent_level + 2)
            for expr_line in expr_lines:
                if expr_line:
                    lines.append(f"{expr_indent}{expr_line}")
                else:
                    lines.append("")
        else:
            expr_text = (expr_lines[0] if expr_lines else "").strip()
            if expr_text:
                lines.append(f"{decl} = {expr_text}")
            else:
                lines.append(decl)
        return lines

    def _needs_backticks(self, expression: str | list[str] | None) -> bool:
        """Check if an expression needs triple-backtick enclosure.

        Since the parser's ``_collect_indented_content`` now uses raw source
        lines, most expression content survives a round-trip without backtick
        protection.  Backticks are only needed when the content would cause
        the TMDL **lexer** to crash or silently consume lines:

        * trailing whitespace — stripped by the lexer's line processing
        * unbalanced single quotes — lexer raises ``Unterminated quoted name``
        * unclosed double quotes — lexer triggers multi-line dq-string
          handling, consuming subsequent lines and corrupting indentation
        * comment lines (``//`` but not ``///``) — skipped entirely by the
          lexer, so they would be lost without backtick protection
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

            # Comment lines (// but not ///) are stripped by the lexer
            # during non-backtick tokenization.
            stripped_for_comment = line.lstrip("\t ")
            if (
                len(stripped_for_comment) >= 2
                and stripped_for_comment[0] == "/"
                and stripped_for_comment[1] == "/"
                and (len(stripped_for_comment) < 3 or stripped_for_comment[2] != "/")
            ):
                return True

            # Unbalanced single quotes — would crash the lexer with
            # "Unterminated quoted name".  Walk the line tracking open/close.
            if "'" in line:
                i = 0
                n_l = len(line)
                while i < n_l:
                    if line[i] == "'":
                        # Opening quote — scan for closing
                        i += 1
                        closed = False
                        while i < n_l:
                            if line[i] == "'":
                                if i + 1 < n_l and line[i + 1] == "'":
                                    i += 2  # escaped '' inside quoted name
                                else:
                                    i += 1
                                    closed = True
                                    break
                            else:
                                i += 1
                        if not closed:
                            return True
                    else:
                        i += 1

            # Unclosed double quotes — would trigger multi-line dq-string
            # handling in the lexer, consuming subsequent lines.
            if '"' in line:
                i = 0
                n_l = len(line)
                while i < n_l:
                    c = line[i]
                    # Skip #"..." M quoted identifiers
                    if c == "#" and i + 1 < n_l and line[i + 1] == '"':
                        i += 2
                        while i < n_l:
                            if line[i] == '"':
                                if i + 1 < n_l and line[i + 1] == '"':
                                    i += 2
                                else:
                                    i += 1
                                    break
                            else:
                                i += 1
                        continue
                    if c == '"':
                        j = i + 1
                        found_close = False
                        while j < n_l:
                            if line[j] == '"':
                                if j + 1 < n_l and line[j + 1] == '"':
                                    j += 2
                                else:
                                    found_close = True
                                    j += 1
                                    break
                            else:
                                j += 1
                        if not found_close:
                            return True
                        i = j
                        continue
                    i += 1

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
            decl = f"{indent}column {self._quote_name(column.name)}"
            lines.extend(self._write_expr_block(decl, column.expression, indent_level))
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
                decl = f"{self._indent(prop_indent)}extendedProperty {ep_name}"
                lines.extend(self._write_expr_block(decl, ep_expr, prop_indent))

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
        decl = f"{indent}measure {self._quote_name(measure.name)}"
        lines.extend(self._write_expr_block(decl, measure.expression, indent_level))

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
                decl = f"{self._indent(prop_indent)}formatStringDefinition"
                lines.extend(self._write_expr_block(decl, expr, prop_indent))

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
                decl = f"{self._indent(prop_indent)}extendedProperty {ep_name}"
                lines.extend(self._write_expr_block(decl, ep_expr, prop_indent))

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
            decl = f"{self._indent(prop_indent)}source"
            lines.extend(self._write_expr_block(decl, source.expression, prop_indent))
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

        # Annotations (with empty line before first and between each)
        if table.annotations:
            if lines and lines[-1] != "":
                lines.append("")
            for i, ann in enumerate(table.annotations):
                lines.append(self._write_annotation(ann, 1))
                if i < len(table.annotations) - 1:
                    lines.append("")  # Empty line between annotations

        # Changed properties
        if table.changedProperties:
            if lines and lines[-1] != "":
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
            if lines and lines[-1] != "":
                lines.append("")
            for ann in hierarchy["annotations"]:
                lines.append(self._write_annotation(ann, prop_indent))
            lines.append("")  # Trailing blank after hierarchy (before next section)

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

        # Cross filtering (comes before cardinality in TMDL)
        if relationship.crossFilteringBehavior:
            lines.append(
                f"\tcrossFilteringBehavior: {relationship.crossFilteringBehavior}"
            )

        # Cardinality and security (order: toCardinality, securityFiltering, fromCardinality)
        if relationship.toCardinality:
            lines.append(f"\ttoCardinality: {relationship.toCardinality}")

        if relationship.securityFilteringBehavior:
            lines.append(
                f"\tsecurityFilteringBehavior: {relationship.securityFilteringBehavior}"
            )

        if relationship.fromCardinality:
            lines.append(f"\tfromCardinality: {relationship.fromCardinality}")

        # joinOnDateBehavior must come before fromColumn/toColumn (matches TMDL source order)
        if relationship.joinOnDateBehavior:
            lines.append(f"\tjoinOnDateBehavior: {relationship.joinOnDateBehavior}")

        # From/To columns (formatted as Table.Column or 'Table Name'.'Column Name')
        from_table = self._quote_name(relationship.fromTable)
        from_col = self._quote_name(relationship.fromColumn)
        to_table = self._quote_name(relationship.toTable)
        to_col = self._quote_name(relationship.toColumn)

        lines.append(f"\tfromColumn: {from_table}.{from_col}")
        lines.append(f"\ttoColumn: {to_table}.{to_col}")

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
        indent_level = 0  # named expressions are root-level objects
        decl = f"expression {self._quote_name(expression.name)}"
        lines.extend(self._write_expr_block(decl, expression.expression, indent_level))

        # Properties
        prop_indent = indent_level + 1

        if expression.lineageTag:
            lines.append(f"{self._indent(prop_indent)}lineageTag: {expression.lineageTag}")

        if expression.sourceLineageTag:
            lines.append(f"{self._indent(prop_indent)}sourceLineageTag: {expression.sourceLineageTag}")

        if expression.queryGroup:
            lines.append(f"{self._indent(prop_indent)}queryGroup: {expression.queryGroup}")

        if expression.kind:
            lines.append(f"{self._indent(prop_indent)}kind: {expression.kind}")

        if expression.mAttributes:
            lines.append(f"{self._indent(prop_indent)}mAttributes: {expression.mAttributes}")

        # Annotations (with empty line before first and between each)
        if expression.annotations:
            lines.append("")  # Empty line before annotations
            for i, ann in enumerate(expression.annotations):
                lines.append(self._write_annotation(ann, prop_indent))
                if i < len(expression.annotations) - 1:
                    lines.append("")  # Empty line between annotations

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

        if model.discourageImplicitMeasures:
            lines.append(f"\tdiscourageImplicitMeasures")

        if model.sourceQueryCulture:
            lines.append(f"\tsourceQueryCulture: {model.sourceQueryCulture}")

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

        # QueryGroup blocks (top-level, before model annotations)
        if model.queryGroups:
            if lines and lines[-1] != "":
                lines.append("")
            for qg in model.queryGroups:
                name = qg.get("name") or ""
                lines.append(f"queryGroup {self._quote_name(name)}")
                if qg.get("annotations"):
                    lines.append("")  # blank line before annotations inside queryGroup
                    for ann in qg["annotations"]:
                        lines.append(self._write_annotation(ann, 1))
                lines.append("")  # blank line after queryGroup block

        # Annotations (with empty line after each)
        if model.annotations:
            if lines and lines[-1] != "":
                lines.append("")  # Blank line before annotations
            for ann in model.annotations:
                lines.append(self._write_annotation(ann, 0))
                lines.append("")  # Empty line after each annotation

        # Table refs — add blank line separator only if the last line isn't already blank
        tables_to_ref = tables or model.tables
        if tables_to_ref:
            if lines and lines[-1] != "":
                lines.append("")
            for table in tables_to_ref:
                lines.append(f"ref table {self._quote_name(table.name)}")

        # Role refs (between table refs and culture refs, with blank separator)
        if model.roles:
            if lines and lines[-1] != "":
                lines.append("")
            for role in model.roles:
                role_name = role.get("name", "") if isinstance(role, dict) else str(role)
                if role_name:
                    lines.append(f"ref role {self._quote_name(role_name)}")

        # Culture refs
        if model.cultures:
            if lines and lines[-1] != "":
                lines.append("")
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
        """Sanitize a name for use as a filename.

        Percent-encodes characters that are invalid in Windows filenames,
        matching Power BI Desktop's convention (e.g. '/' → '%2F', '>' → '%3E').
        """
        from urllib.parse import quote

        # Characters invalid in Windows filenames
        invalid_chars = set('<>:"/\\|?*')
        result = []
        for char in name:
            if char in invalid_chars:
                result.append(quote(char, safe=""))
            else:
                result.append(char)
        return "".join(result)

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
