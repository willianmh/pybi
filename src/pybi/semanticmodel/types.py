from typing import Literal

SourceType = Literal["calculated", "calculationGroup", "entity", "m"]

PartitionMode = Literal["directQuery", "import"]

"""Supported data types
See: https://learn.microsoft.com/en-us/dotnet/api/microsoft.analysisservices.tabular.datatype?view=analysisservices-dotnet"""
DataType = Literal[
    "binary",
    "boolean",
    "dateTime",
    "decimal",
    "double",
    "int64",
    "string",
    "unknown",
    "variant",
]

DataCategory = Literal[
    "DayOfMonth",
    "ImageUrl",
    "MonthOfYear",
    "Months",
    "PaddedDateTableDates",
    "QuarterOfYear",
    "Quarters",
    "Uncategorized",
    "WebUrl",
    "Years",
]


ColumnType = Literal["calculated", "calculatedTableColumn"]
