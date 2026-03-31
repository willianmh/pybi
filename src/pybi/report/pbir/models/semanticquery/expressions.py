"""The Expressions were taken from
json-schemas/fabric/item/report/definition/semanticQuery/1.4.0/schema.json
"""

from __future__ import annotations

from typing import Any
from typing_extensions import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_serializer

# ---------------------------------------------------------------------------
# Forward reference handling for recursive types
# ---------------------------------------------------------------------------

# These will be populated after all classes are defined
_EXPRESSION_TYPE_MAP: dict[str, Any] = {}


def _parse_expression_container(data: Any) -> QueryExpressionContainer | None:
    """Parse a dict into the appropriate QueryExpressionContainer.

    This validator examines the dict keys to determine which expression type
    is present, then instantiates the corresponding class.
    """
    if data is None:
        return None
    if isinstance(data, QueryExpressionContainer):
        return data
    if not isinstance(data, dict):
        return data

    # Extract metadata fields that can appear alongside any expression
    name = data.get("Name")
    native_ref_name = data.get("NativeReferenceName")
    annotations = data.get("Annotations")

    # Find the expression type key (the one that's not a metadata field)
    expr_key = None
    expr_value = None
    for key, value in data.items():
        if key not in ("Name", "NativeReferenceName", "Annotations"):
            expr_key = key
            expr_value = value
            break

    if expr_key is None:
        # No expression type found - return empty container
        return QueryExpressionContainer(
            Name=name,
            NativeReferenceName=native_ref_name,
            Annotations=annotations,
        )

    # Look up the expression type class or parser function
    expr_handler = _EXPRESSION_TYPE_MAP.get(expr_key)
    if expr_handler is None:
        # Unknown expression type - preserve raw payload via explicit fallback
        return QueryExpressionContainer(
            Name=name,
            NativeReferenceName=native_ref_name,
            Annotations=annotations,
            _expression_type=expr_key,
            _expression=UnknownExpression(raw=expr_value),
            _expression_data=expr_value,
        )

    # Instantiate the expression
    if isinstance(expr_value, dict):
        # Check if handler is a parser function (callable but not a class)
        if callable(expr_handler) and not isinstance(expr_handler, type):
            expr_instance = expr_handler(expr_value)
        else:
            expr_instance = expr_handler(**expr_value)
    else:
        expr_instance = expr_value

    return QueryExpressionContainer(
        Name=name,
        NativeReferenceName=native_ref_name,
        Annotations=annotations,
        _expression_type=expr_key,
        _expression=expr_instance,
    )


# Type alias for recursive expression references
ParsedExpressionContainer = Annotated[
    "QueryExpressionContainer | None", BeforeValidator(_parse_expression_container)
]


# ---------------------------------------------------------------------------
# Base Expression Class
# ---------------------------------------------------------------------------


class Expression(BaseModel):
    """Base class for all expression types."""

    model_config = ConfigDict(
        extra="allow",  # Allow extra fields for forward compatibility
        populate_by_name=True,
    )

    @model_serializer(mode="wrap")
    def _serialize(self, handler: Any) -> dict[str, Any]:
        """Serialize the expression to a dict with only non-None fields."""
        result = {}
        for field_name, field_info in self.__class__.model_fields.items():
            value = getattr(self, field_name)
            if value is not None:
                # Handle alias
                alias = field_info.alias or field_name
                if isinstance(value, BaseModel):
                    result[alias] = value.model_dump(by_alias=True, exclude_none=True)
                elif isinstance(value, list):
                    result[alias] = [
                        (
                            v.model_dump(by_alias=True, exclude_none=True)
                            if isinstance(v, BaseModel)
                            else v
                        )
                        for v in value
                    ]
                else:
                    result[alias] = value
        return result


class UnknownExpression(Expression):
    """Fallback wrapper for unrecognized expression variants."""

    raw: Any = None


# ---------------------------------------------------------------------------
# Source Reference Expressions
# ---------------------------------------------------------------------------


class StandaloneSourceRefExpression(Expression):
    """Standalone source reference to an entity in data."""

    Schema_: str | None = Field(default=None, alias="Schema")
    Entity: str


class QuerySourceRefExpression(Expression):
    """Source reference within a query context."""

    Source: str


def _parse_source_ref(data: dict) -> Expression:
    """Parse SourceRef which can be either standalone or query-based."""
    if "Source" in data:
        return QuerySourceRefExpression(**data)
    else:
        return StandaloneSourceRefExpression(**data)


# ---------------------------------------------------------------------------
# Property/Field Reference Expressions
# ---------------------------------------------------------------------------


class QueryColumnExpression(Expression):
    """Reference to a column in a source table."""

    Expression: ParsedExpressionContainer
    Property: str


class QueryMeasureExpression(Expression):
    """Reference to a measure in a source table."""

    Expression: ParsedExpressionContainer
    Property: str


class QueryHierarchyExpression(Expression):
    """Reference to a hierarchy in a source table."""

    Expression: ParsedExpressionContainer
    Hierarchy: str


class QueryHierarchyLevelExpression(Expression):
    """Reference to a level within a hierarchy."""

    Expression: ParsedExpressionContainer
    Level: str


class QueryPropertyVariationSourceExpression(Expression):
    """Reference to a source of variations associated with a property."""

    Expression: ParsedExpressionContainer
    Name: str
    Property: str


class QueryGroupRefExpression(Expression):
    """Reference to a model grouping column."""

    Expression: ParsedExpressionContainer
    Property: str
    GroupedColumns: list[ParsedExpressionContainer]


# ---------------------------------------------------------------------------
# Aggregation Expressions
# ---------------------------------------------------------------------------


class QueryAggregationExpression(Expression):
    """Aggregation of an expression."""

    Expression: ParsedExpressionContainer
    Function: int  # QueryAggregateFunction enum value


class QueryMinExpression(Expression):
    """Min aggregation expression."""

    Expression: ParsedExpressionContainer
    IncludeAllTypes: int  # IncludeAllTypes enum value


class QueryMaxExpression(Expression):
    """Max aggregation expression."""

    Expression: ParsedExpressionContainer
    IncludeAllTypes: int  # IncludeAllTypes enum value


class QueryPercentileExpression(Expression):
    """Percentile calculation expression."""

    Expression: ParsedExpressionContainer
    K: float
    Exclusive: bool = False


# ---------------------------------------------------------------------------
# Logical/Boolean Expressions
# ---------------------------------------------------------------------------


class QueryBinaryExpression(Expression):
    """Binary expression (And, Or, etc.) with two operands."""

    Left: ParsedExpressionContainer
    Right: ParsedExpressionContainer


class QueryNotExpression(Expression):
    """Negation expression."""

    Expression: ParsedExpressionContainer


class QueryContainsExpression(Expression):
    """Contains comparison expression."""

    Left: ParsedExpressionContainer
    Right: ParsedExpressionContainer


class QueryStartsWithExpression(Expression):
    """StartsWith comparison expression."""

    Left: ParsedExpressionContainer
    Right: ParsedExpressionContainer


class QueryExistsExpression(Expression):
    """Exists expression - confirms existence of at least one instance."""

    Expression: ParsedExpressionContainer


class QueryComparisonExpression(Expression):
    """Comparison expression between two operands."""

    ComparisonKind: int  # QueryComparisonKind enum value
    Left: ParsedExpressionContainer
    Right: ParsedExpressionContainer


class QueryInExpression(Expression):
    """In expression - checks if tuple matches any value tuple."""

    Expressions: list[ParsedExpressionContainer]
    Values: list[list[ParsedExpressionContainer]] | None = None
    Table: ParsedExpressionContainer | None = None


class QueryBetweenExpression(Expression):
    """Between expression - checks if value is within bounds."""

    Expression: ParsedExpressionContainer
    LowerBound: ParsedExpressionContainer
    UpperBound: ParsedExpressionContainer


# ---------------------------------------------------------------------------
# Literal and Value Expressions
# ---------------------------------------------------------------------------


class QueryLiteralExpression(Expression):
    """Literal value expression."""

    Value: str


class QueryDefaultValueExpression(Expression):
    """Model-defined default value for a column."""

    pass


class QueryAnyValueExpression(Expression):
    """Wildcard value that matches any value."""

    DefaultValueOverridesAncestors: bool | None = None


class QueryNowExpression(Expression):
    """Current date and time expression."""

    pass


# ---------------------------------------------------------------------------
# Date/Time Expressions
# ---------------------------------------------------------------------------


class QueryDateSpanExpression(Expression):
    """DateSpan calculation expression."""

    Expression: ParsedExpressionContainer
    TimeUnit: int  # TimeUnit enum value


class QueryDateAddExpression(Expression):
    """DateAdd calculation expression."""

    Expression: ParsedExpressionContainer
    Amount: int
    TimeUnit: int  # TimeUnit enum value


# ---------------------------------------------------------------------------
# Arithmetic Expressions
# ---------------------------------------------------------------------------


class QueryArithmeticExpression(Expression):
    """Arithmetic operation on two expressions."""

    Left: ParsedExpressionContainer
    Right: ParsedExpressionContainer
    Operator: int  # ArithmeticOperatorKind enum value


class QueryFloorExpression(Expression):
    """Floor/rounding operation."""

    Expression: ParsedExpressionContainer
    Size: float
    TimeUnit: int | None = None


class QueryDiscretizeExpression(Expression):
    """Discretization of continuous values."""

    Expression: ParsedExpressionContainer
    Count: int


# ---------------------------------------------------------------------------
# Scoped/Filtered Evaluation Expressions
# ---------------------------------------------------------------------------


class QueryScopedEvalExpression(Expression):
    """Expression evaluated in a specified scope."""

    Expression: ParsedExpressionContainer
    Scope: list[ParsedExpressionContainer]


class QueryFilteredEvalExpression(Expression):
    """Expression with filters applied."""

    Expression: ParsedExpressionContainer
    Filters: list["QueryFilter"]


# ---------------------------------------------------------------------------
# Subquery and Transform Expressions
# ---------------------------------------------------------------------------


class QuerySubqueryExpression(Expression):
    """Subquery expression holding a nested query."""

    Query: "QueryDefinition"


class QueryTransformTableRefExpression(Expression):
    """Reference to a TransformTable in the query."""

    Source: str


class QueryTransformOutputRoleRefExpression(Expression):
    """Reference to a column produced by a Transform algorithm."""

    Role: str
    Transform: str | None = None


# ---------------------------------------------------------------------------
# Visual/Sparkline Expressions
# ---------------------------------------------------------------------------


class QuerySparklineDataExpression(Expression):
    """Sparkline data representation."""

    Measure: ParsedExpressionContainer
    Groupings: list[ParsedExpressionContainer]
    PointsPerSparkline: int | None = None
    ApplyCalculationGroupTo: str | None = None


class QueryVisualTopNExpression(Expression):
    """Visual TopN filter expression."""

    ItemCount: int


# ---------------------------------------------------------------------------
# Native Expressions (DAX, etc.)
# ---------------------------------------------------------------------------


class QueryExpressionContentCache(Expression):
    """Metadata about native expression content."""

    Dependencies: list[ParsedExpressionContainer] | None = None
    UnrecognizedIdentifiers: bool | None = None


class QueryNativeVisualCalc(Expression):
    """Native visual calculation expression (DAX)."""

    Language: str  # "dax"
    Expression: str
    Name: str
    DataType: str | None = None


class QueryNativeMeasure(Expression):
    """Native measure definition (DAX)."""

    DataType: int
    Expression: str
    Language: str  # "dax"
    ExpressionContentCache: QueryExpressionContentCache | None = None
    ProposedName: str | None = None
    Format: str | None = None


class QueryNativeColumn(Expression):
    """Native column definition."""

    DataType: int
    Expression: str
    Language: str
    Source: ParsedExpressionContainer
    ExpressionContentCache: QueryExpressionContentCache | None = None
    ProposedName: str | None = None
    Format: str | None = None


# ---------------------------------------------------------------------------
# Formatting/Color Expressions
# ---------------------------------------------------------------------------


class QueryFillRuleExpression(Expression):
    """Dynamic fill rule expression."""

    Input: ParsedExpressionContainer
    FillRule: Any  # Complex fill rule definition


class QueryThemeDataColorExpression(Expression):
    """Theme color selection expression."""

    ColorId: int
    Percent: float


class QueryConditionalExpression(Expression):
    """Conditional expression with cases and default."""

    Cases: list["QueryCase"]
    DefaultValue: ParsedExpressionContainer | None = None


class QueryCase(Expression):
    """A single case in a conditional expression."""

    Condition: ParsedExpressionContainer
    Value: ParsedExpressionContainer


# ---------------------------------------------------------------------------
# Reference Expressions
# ---------------------------------------------------------------------------


class QueryResourcePackageItem(Expression):
    """Reference to a ResourcePackage item."""

    PackageName: str
    PackageType: int
    ItemName: str


class QueryRoleRefExpression(Expression):
    """Reference to a named Role in a Visual."""

    Role: str


class QuerySummaryValueRefExpression(Expression):
    """Reference to a summary value in Insights Summary."""

    Name: str


class QueryAllRolesRefExpression(Expression):
    """Reference to all roles in a visual."""

    pass


class QuerySelectRefExpression(Expression):
    """Reference to a named item in the select clause."""

    ExpressionName: str


# ---------------------------------------------------------------------------
# Query Structure Types
# ---------------------------------------------------------------------------


class EntitySource(Expression):
    """Source table definition in a query."""

    Name: str
    Entity: str | None = None
    Schema_: str | None = Field(default=None, alias="Schema")
    Expression: ParsedExpressionContainer | None = None
    Type: int | None = None


class QueryFilter(Expression):
    """Filter definition in a query."""

    Condition: ParsedExpressionContainer
    Target: list[ParsedExpressionContainer] | None = None
    Annotations: dict[str, Any] | None = None


class QuerySortClause(Expression):
    """Sort clause in a query."""

    Direction: int  # SortDirection enum value
    Expression: ParsedExpressionContainer


class AxisGroup(Expression):
    """Axis group definition."""

    Keys: list[ParsedExpressionContainer]
    Subtotal: bool


class Axis(Expression):
    """Axis definition in a query."""

    Name: str
    Groups: list[AxisGroup]


class QueryTransformTableColumn(Expression):
    """Column in a transform table."""

    Expression: ParsedExpressionContainer
    Role: str | None = None


class QueryTransformTable(Expression):
    """Transform table definition."""

    Name: str
    Columns: list[QueryTransformTableColumn]


class QueryTransformInput(Expression):
    """Input for a transform operation."""

    Parameters: list[ParsedExpressionContainer]
    Table: QueryTransformTable | None = None


class QueryTransformOutput(Expression):
    """Output from a transform operation."""

    Table: QueryTransformTable | None = None


class QueryTransform(Expression):
    """Transform operation definition."""

    Name: str
    Algorithm: str
    Input: QueryTransformInput
    Output: QueryTransformOutput


class QueryDefinition(Expression):
    """Complete query definition."""

    Version: int | None = None
    From: list[EntitySource]
    Select: list[ParsedExpressionContainer]
    Where: list[QueryFilter] | None = None
    OrderBy: list[QuerySortClause] | None = None
    GroupBy: list[ParsedExpressionContainer] | None = None
    Transform: list[QueryTransform] | None = None
    VisualShape: list[Axis] | None = None
    Top: int | None = None


class FilterDefinition(Expression):
    """Filter element as a partial query structure.

    ``From`` is optional because visual-level filters may omit it (Power BI
    infers the source tables from the visual context at render time).
    """

    Version: int | None = None
    From: list[EntitySource] | None = None
    Where: list[QueryFilter]


# ---------------------------------------------------------------------------
# QueryExpressionContainer - The main container class
# ---------------------------------------------------------------------------


class QueryExpressionContainer(BaseModel):
    """Container holding a single expression with associated metadata.

    This is the main entry point for expression parsing. Each instance contains
    exactly one expression type (Column, Measure, Not, And, etc.) along with
    optional metadata (Name, NativeReferenceName, Annotations).

    The expression type is determined by examining the dict keys when parsing.
    """

    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
    )

    # Metadata fields that can appear with any expression
    Name: str | None = None
    NativeReferenceName: str | None = None
    Annotations: dict[str, Any] | None = None

    # Internal fields for tracking the expression (excluded from serialization)
    _expression_type: str | None = None
    _expression: Expression | None = None
    _expression_data: Any = None  # For unknown expression types

    def __init__(self, **data: Any) -> None:
        """Initialize with expression type detection.

        When constructed directly (not via ParsedExpressionContainer), the dict
        may contain expression keys like 'Column', 'Measure', etc. These are
        detected and parsed automatically.
        """
        # Extract internal fields if already parsed (e.g., from BeforeValidator)
        expr_type = data.pop("_expression_type", None)
        expr_instance = data.pop("_expression", None)
        expr_data = data.pop("_expression_data", None)

        # If not already parsed, detect expression keys in the data
        if expr_type is None and expr_instance is None:
            metadata_fields = {"Name", "NativeReferenceName", "Annotations"}
            for key in list(data.keys()):
                if key in _EXPRESSION_TYPE_MAP:
                    expr_type = key
                    expr_value = data.pop(key)
                    handler = _EXPRESSION_TYPE_MAP[key]
                    try:
                        if callable(handler) and not isinstance(handler, type):
                            expr_instance = handler(expr_value)
                        elif isinstance(expr_value, dict):
                            expr_instance = handler(**expr_value)
                        else:
                            expr_data = expr_value
                    except Exception:
                        expr_data = expr_value
                    break
                if key not in metadata_fields:
                    expr_type = key
                    expr_value = data.pop(key)
                    expr_instance = UnknownExpression(raw=expr_value)
                    expr_data = expr_value
                    break

        super().__init__(**data)

        # Store internal tracking fields using object.__setattr__ to bypass Pydantic
        object.__setattr__(self, "_expression_type", expr_type)
        object.__setattr__(self, "_expression", expr_instance)
        object.__setattr__(self, "_expression_data", expr_data)

    @model_serializer(mode="wrap")
    def _serialize(self, handler: Any) -> dict[str, Any]:
        """Serialize back to the original dict format.

        Expression key comes first, metadata (Name, NativeReferenceName,
        Annotations) follows : matching the source JSON field order.
        """
        result: dict[str, Any] = {}

        # Add the expression with its type key first
        expr_type = self._expression_type
        expr = self._expression
        expr_data = self._expression_data

        if expr_type and expr is not None:
            if isinstance(expr, UnknownExpression):
                result[expr_type] = expr.raw
            elif isinstance(expr, BaseModel):
                result[expr_type] = expr.model_dump(by_alias=True, exclude_none=True)
            else:
                result[expr_type] = expr
        elif expr_type and expr_data is not None:
            result[expr_type] = expr_data

        # Add metadata fields after the expression key
        if self.Name is not None:
            result["Name"] = self.Name
        if self.NativeReferenceName is not None:
            result["NativeReferenceName"] = self.NativeReferenceName
        if self.Annotations is not None:
            result["Annotations"] = self.Annotations

        return result

    def get_expression(self) -> Expression | None:
        """Get the contained expression instance."""
        return self._expression

    def get_expression_type(self) -> str | None:
        """Get the type name of the contained expression."""
        return self._expression_type


# ---------------------------------------------------------------------------
# Register expression types for the parser
# ---------------------------------------------------------------------------

_EXPRESSION_TYPE_MAP.update(
    {
        "SourceRef": _parse_source_ref,  # Special handler for SourceRef variants
        "Column": QueryColumnExpression,
        "Measure": QueryMeasureExpression,
        "Min": QueryMinExpression,
        "Max": QueryMaxExpression,
        "Aggregation": QueryAggregationExpression,
        "Percentile": QueryPercentileExpression,
        "Hierarchy": QueryHierarchyExpression,
        "HierarchyLevel": QueryHierarchyLevelExpression,
        "PropertyVariationSource": QueryPropertyVariationSourceExpression,
        "Subquery": QuerySubqueryExpression,
        "Discretize": QueryDiscretizeExpression,
        "And": QueryBinaryExpression,
        "Between": QueryBetweenExpression,
        "In": QueryInExpression,
        "Or": QueryBinaryExpression,
        "Comparison": QueryComparisonExpression,
        "Not": QueryNotExpression,
        "Contains": QueryContainsExpression,
        "StartsWith": QueryStartsWithExpression,
        "Exists": QueryExistsExpression,
        "Literal": QueryLiteralExpression,
        "DateSpan": QueryDateSpanExpression,
        "DateAdd": QueryDateAddExpression,
        "Now": QueryNowExpression,
        "DefaultValue": QueryDefaultValueExpression,
        "AnyValue": QueryAnyValueExpression,
        "Arithmetic": QueryArithmeticExpression,
        "Floor": QueryFloorExpression,
        "ScopedEval": QueryScopedEvalExpression,
        "FilteredEval": QueryFilteredEvalExpression,
        "TransformTableRef": QueryTransformTableRefExpression,
        "TransformOutputRoleRef": QueryTransformOutputRoleRefExpression,
        "SparklineData": QuerySparklineDataExpression,
        "NativeVisualCalculation": QueryNativeVisualCalc,
        "FillRule": QueryFillRuleExpression,
        "GroupRef": QueryGroupRefExpression,
        "ResourcePackageItem": QueryResourcePackageItem,
        "RoleRef": QueryRoleRefExpression,
        "SummaryValueRef": QuerySummaryValueRefExpression,
        "AllRolesRef": QueryAllRolesRefExpression,
        "SelectRef": QuerySelectRefExpression,
        "ThemeDataColor": QueryThemeDataColorExpression,
        "Conditional": QueryConditionalExpression,
        "NativeMeasure": QueryNativeMeasure,
        "NativeColumn": QueryNativeColumn,
        "VisualTopN": QueryVisualTopNExpression,
    }
)
