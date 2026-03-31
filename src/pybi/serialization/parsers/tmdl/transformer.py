import json
from typing import Any

from .exceptions import TMDLTransformError
from .grammar import (
    CHILDREN_NAMING_MAP,
    parse_column_reference,
    unquote_name,
)
from .parser import ObjectDeclaration
from ....semanticmodel.definition import (
    Column,
    Culture,
    Expression,
    Measure,
    Model,
    Partition,
    Relationship,
    Source,
    Table,
)


def _normalize_expr(raw: str | None) -> str | list[str] | None:
    """Normalize a raw TMDL expression string to relative (0-based) indentation.

    This mirrors the normalization that ``TMDLWriter._normalize_expression_lines``
    applies on write, so that the stored model value is stable across round-trips
    regardless of the absolute indentation in the source file.

    Steps:
    1. Strip leading/trailing whitespace from the full string.
    2. Split into lines.
    3. Strip the minimum common leading-tab count from every non-empty line.
       If the first non-empty line lost its leading tabs via the strip in step 1
       (i.e. it has 0 tabs but subsequent lines have common indentation), use the
       minimum of the *remaining* lines as the base indent to strip.
    """
    if not raw:
        return None
    stripped = raw.strip()
    if not stripped:
        return None
    lines = stripped.split("\n")
    if len(lines) == 1:
        return lines[0]

    non_empty = [l for l in lines if l.strip()]
    if not non_empty:
        return lines

    tab_counts = [len(l) - len(l.lstrip("\t")) for l in non_empty]
    min_tabs = min(tab_counts)

    if min_tabs == 0 and len(tab_counts) > 1:
        remaining = [c for c in tab_counts[1:]]
        if remaining and min(remaining) > 0:
            min_tabs = min(remaining)

    if min_tabs == 0:
        return lines

    result = []
    for line in lines:
        if len(line) >= min_tabs and line[:min_tabs] == "\t" * min_tabs:
            result.append(line[min_tabs:])
        else:
            result.append(line)
    return result


def _normalize_changed_properties(raw_list: list) -> list[dict]:
    """Convert raw changedProperty node dicts to ``{"property": name}`` form.

    The TMDL parser produces ``{"expression": "PropName", "name": None}`` for
    ``changedProperty = PropName``.  The writer expects ``{"property": "PropName"}``.
    """
    return [
        {"property": cp.get("expression", cp.get("name", ""))}
        for cp in raw_list
        if isinstance(cp, dict)
    ]


def expand_node(node: ObjectDeclaration) -> dict:
    """Merge properties and children of an AST node into a flat dict.

    Child object types are mapped through ``CHILDREN_NAMING_MAP`` so that
    singular TMDL keywords (e.g. ``annotation``) become the plural field
    names expected by Pydantic models (e.g. ``annotations``).
    """
    expanded = {p.key: p.value for p in node.properties}

    expanded["name"] = node.name
    if node.expression is not None:
        expanded["expression"] = node.expression
    if node.description is not None:
        expanded["description"] = node.description

    for c in node.children:
        key = CHILDREN_NAMING_MAP.get(c.object_type, c.object_type)
        child_data = expand_node(c)
        if key in expanded:
            expanded[key].append(child_data)
        else:
            expanded[key] = [child_data]
    return expanded


class TMDLTransformer:
    """Transforms TMDL AST nodes into Pydantic models."""

    def __init__(self, file_path: str | None = None):
        self.file_path = file_path

    def _error(self, message: str, line: int | None = None) -> TMDLTransformError:
        return TMDLTransformError(message, line=line, file_path=self.file_path)

    def transform_database(self, node: ObjectDeclaration) -> int:
        """Transform a database node to get compatibilityLevel."""
        raw = expand_node(node)
        return int(raw.get("compatibilityLevel", 1600))

    def transform_expression(self, node: ObjectDeclaration) -> Expression:
        """Transform an expression node to an Expression model."""
        raw = expand_node(node)
        raw["expression"] = _normalize_expr(node.expression) or ""
        return Expression.model_validate(raw)

    def transform_column(self, node: ObjectDeclaration) -> Column:
        """Transform a column node to a Column model."""
        raw = expand_node(node)
        if node.expression is not None:
            raw["type"] = "calculated"
            normalized = _normalize_expr(node.expression)
            raw["expression"] = (
                "\n".join(normalized) if isinstance(normalized, list) else normalized
            )
        # Rewrite changedProperty dicts from {name, expression} to {property}
        if "changedProperties" in raw:
            raw["changedProperties"] = _normalize_changed_properties(
                raw["changedProperties"]
            )
        # sortByColumn is a quoted name in TMDL (e.g. 'Calendar Month');
        # unquote it so the writer can re-quote canonically without doubling.
        if "sortByColumn" in raw and isinstance(raw["sortByColumn"], str):
            raw["sortByColumn"] = unquote_name(raw["sortByColumn"])
        # Normalize extendedProperties expressions for stable round-trips
        if "extendedProperties" in raw:
            for ep in raw["extendedProperties"]:
                if "expression" in ep and ep["expression"]:
                    ep["expression"] = _normalize_expr(ep["expression"]) or ""
        return Column.model_validate(raw)

    def transform_measure(self, node: ObjectDeclaration) -> Measure:
        """Transform a measure node to a Measure model."""
        raw = expand_node(node)
        raw["expression"] = _normalize_expr(node.expression) or ""
        # formatStringDefinition children -> dict with "expression" key
        fsd_list = raw.pop("formatStringDefinition", None)
        if fsd_list:
            raw["formatStringDefinition"] = {
                "expression": fsd_list[0].get("expression")
            }
        if "changedProperties" in raw:
            raw["changedProperties"] = _normalize_changed_properties(
                raw["changedProperties"]
            )
        # Normalize extendedProperties expressions for stable round-trips
        if "extendedProperties" in raw:
            for ep in raw["extendedProperties"]:
                if "expression" in ep and ep["expression"]:
                    ep["expression"] = _normalize_expr(ep["expression"]) or ""
        return Measure.model_validate(raw)

    def transform_partition(self, node: ObjectDeclaration) -> Partition:
        """Transform a partition node to a Partition model."""
        raw = expand_node(node)
        mode = raw.get("mode", "import")

        source_data: dict[str, Any] = {"type": "m"}
        source_children = raw.pop("source", None)
        if source_children:
            src = source_children[0]
            # (1) explicit type property
            source_type = src.get("type")
            if source_type:
                source_data["type"] = source_type
            # (2) entity source overrides type
            entity_name = src.get("entityName")
            if entity_name:
                source_data["type"] = "entity"
                source_data["entityName"] = entity_name
            # expressionSource (used by both entity and calculated)
            expr_source = src.get("expressionSource")
            if expr_source:
                source_data["expressionSource"] = unquote_name(expr_source)
            # (3) M expression on source child overrides type
            if src.get("expression"):
                source_data["type"] = "m"
                source_data["expression"] = _normalize_expr(src["expression"])

        # Partition-level expression determines source type
        if node.expression:
            part_type = node.expression.strip().lower()
            if part_type in ("entity", "m", "calculated"):
                source_data["type"] = part_type

        return Partition(
            name=node.name or "",
            mode=mode,
            queryGroup=raw.get("queryGroup"),
            source=Source(**source_data),
        )

    def transform_relationship(self, node: ObjectDeclaration) -> Relationship:
        """Transform a relationship node to a Relationship model."""
        raw = expand_node(node)
        from_table, from_column = parse_column_reference(raw.get("fromColumn", ""))
        to_table, to_column = parse_column_reference(raw.get("toColumn", ""))
        raw["fromTable"] = from_table
        raw["fromColumn"] = from_column
        raw["toTable"] = to_table
        raw["toColumn"] = to_column
        return Relationship.model_validate(raw)

    def transform_table(self, node: ObjectDeclaration) -> Table:
        """Transform a table node to a Table model."""
        raw = expand_node(node)

        if "changedProperties" in raw:
            raw["changedProperties"] = _normalize_changed_properties(
                raw["changedProperties"]
            )

        # Transform typed children via dedicated methods
        raw["columns"] = [
            self.transform_column(c) for c in node.children if c.object_type == "column"
        ] or None
        raw["measures"] = [
            self.transform_measure(c)
            for c in node.children
            if c.object_type == "measure"
        ] or None
        raw["partitions"] = [
            self.transform_partition(c)
            for c in node.children
            if c.object_type == "partition"
        ]

        # Hierarchies: expand recursively (no dedicated transform needed)
        hier_children = [c for c in node.children if c.object_type == "hierarchy"]
        if hier_children:
            raw["hierarchies"] = [expand_node(h) for h in hier_children]

        # Remove raw child lists replaced by transformed objects
        for key in ("column", "measure", "partition", "hierarchy"):
            raw.pop(key, None)

        return Table.model_validate(raw)

    def transform_culture(self, node: ObjectDeclaration) -> Culture:
        """Transform a cultureInfo node to a Culture model."""
        raw = expand_node(node)
        name = raw.get("name") or "en-US"

        linguistic_metadata = None
        lm_value = raw.get("linguisticMetadata")
        if lm_value:
            try:
                if isinstance(lm_value, str):
                    linguistic_metadata = {
                        "content": json.loads(lm_value),
                        "contentType": "json",
                    }
            except (json.JSONDecodeError, TypeError):
                linguistic_metadata = {"content": lm_value, "contentType": "json"}

        content_type = raw.get("contentType", "json")
        if linguistic_metadata:
            linguistic_metadata["contentType"] = content_type

        if linguistic_metadata is not None:
            return Culture(name=name, linguisticMetadata=linguistic_metadata)
        return Culture(name=name)

    def transform_model(
        self,
        node: ObjectDeclaration,
        tables: list[Table],
        relationships: list[Relationship],
        expressions: list[Expression],
        cultures: list[Culture],
    ) -> Model:
        """Transform a model node to a Model model."""
        raw = expand_node(node)

        # dataAccessOptions: child with flag properties -> flat dict
        dao_list = raw.pop("dataAccessOptions", None)
        if dao_list:
            raw["dataAccessOptions"] = {
                k: v for k, v in dao_list[0].items() if k not in ("name", "value")
            }

        # Inject externally-loaded collections
        raw["tables"] = tables or None
        raw["relationships"] = relationships or None
        raw["expressions"] = expressions or []
        raw["cultures"] = cultures or [Culture()]

        return Model.model_validate(raw)
