# TMDL : Tabular Model Definition Language

TMDL is Microsoft's text-based format for defining Power BI semantic models (formerly Analysis Services Tabular Models). It is the source-control-friendly alternative to the binary `.pbix` / JSON `.bim` formats, representing the complete Tabular Object Model (TOM) as a folder of human-readable `.tmdl` files.

Compatibility: tabular models at **compatibility level 1200 or higher** (Power BI: `compatibilityLevel: 1567`).

---

## Folder Layout

A TMDL definition folder has one level of sub-folders. Every file has the `.tmdl` extension.

```
definition/
├── database.tmdl          # one file : database-level properties
├── model.tmdl             # one file : model properties + ref ordering
├── relationships.tmdl     # one file : ALL relationships
├── expressions.tmdl       # one file : ALL named M/DAX expressions
├── tables/
│   ├── Sales.tmdl         # one file per table
│   └── Date.tmdl
└── cultures/
    └── en-US.tmdl         # one file per culture (linguistic metadata)
```

Files that may also appear: `roles/`, `perspectives/`, `dataSources.tmdl`, `functions.tmdl`.

All inner metadata of a table (columns, measures, hierarchies, partitions) lives in that table's file.

---

## Syntax Fundamentals

### Indentation

TMDL uses **tab-based indentation** (a single tab per level) to express object nesting. There are three structural levels:

```
table Sales                      ← Level 1: object declaration
	lineageTag: e9374b9a-...     ← Level 2: object property
	measure 'Sales Amount' =     ← Level 2: child object declaration
			SUMX(...)            ← Level 3: multi-line expression body
		formatString: $ #,##0    ← Level 2: property after expression
```

Root-level objects (`table`, `model`, `relationship`, `expression`, etc.) require **no indentation**; they are implicitly children of the database/model.

### Two Assignment Delimiters

| Delimiter | Used for |
|-----------|----------|
| `:` | All regular property values (`dataType: string`, `fromColumn: Sales.Date`) |
| `=` | Default property / expression (`measure X = SUM(...)`, `partition P = m`) |

### Casing

TMDL is **case-insensitive on read**. On write, the serializer emits camelCase for keywords, object types, and enum values (`dataType`, `formatString`, `import`, `datePartOnly`).

---

## Object Declaration

Every TMDL object is declared as:

```
<keyword> <name>
```

Example from `tables/Accounts.tmdl`:
```tmdl
table Accounts
	lineageTag: 22d72ed3-5ee0-4ff1-98ec-c82153839a11
```

### Name Quoting

Names must be enclosed in **single quotes** when they contain any of: space, `.`, `=`, `:`, `'`.

```tmdl
table 'Case Calendar'                   ← space in name
column 'State or Province'              ← space in name
column 'Account Owner'                  ← space in name
relationship 6bf63ad9-...-cb53cdeb7e5a  ← GUID names need no quoting
```

If a name contains a literal single quote, **double it**:

```tmdl
measure 'Sales Amount'''  ← object named: Sales Amount'
```

---

## Properties

### Regular Properties (colon syntax)

```tmdl
column City
	dataType: string
	lineageTag: 03fe1662-8e1f-438b-8060-9d043b9046e6
	dataCategory: City
	summarizeBy: none
	sourceColumn: City
```
From `tables/Accounts.tmdl`.

Text property values may omit surrounding double-quotes unless the value has leading/trailing whitespace. When enclosed in double-quotes, inner double-quotes are escaped by doubling: `"My ""Amazing"" Folder"`.

### Boolean Flag Shorthand

A boolean property set to `true` can be written as just the property name (no value):

```tmdl
table DateTableTemplate_0039983e-...
	isHidden         ← equivalent to: isHidden: true
	isPrivate        ← equivalent to: isPrivate: true
```

From `tables/DateTableTemplate_0039983e-de71-45fb-bd88-812f61c0ff38.tmdl`. To set `false` explicitly, use: `isAvailableInMdx: false`.

### Named Object References (dot notation)

Properties that reference another model object use the object name, with the same quoting rules. Cross-table column references use dot notation:

```tmdl
relationship 6bf63ad9-2603-438b-a700-cb53cdeb7e5a
	fromColumn: Accounts.'Account Owner'   ← quoted because name has space
	toColumn: Owners.'Sales owner'

relationship ab2e21ab-c232-41ff-83dc-8e3b0d908f5e
	fromColumn: Opportunities.AccountSeq   ← no quoting needed
	toColumn: Accounts.AccountSeq
```

From `relationships.tmdl` (AI Sample).

---

## Expressions

Expressions are verbatim text blocks (DAX, M, JSON, etc.) assigned with `=`. They appear as:

### 1. Single-line inline

```tmdl
measure 'Total confirmed cases' = SUM('COVID'[Daily cases])
	formatString: #,0
```

From `tables/COVID measures.tmdl` (COVID-19 US Sample).

### 2. Multi-line (indented)

The expression body starts on the line immediately after the `=` and must be indented **one level deeper than the object's properties**. Trailing blank lines are stripped; blank lines within the body are preserved.

```tmdl
measure 'Opportunity Count' =

		COUNTAX(Opportunities,TRUE())
	formatString: #,0
```

From `tables/Opportunities.tmdl` (AI Sample). Note the property `formatString` sits at the property indentation level (one tab), while the DAX body is at two tabs.

### 3. Backtick-fenced (verbatim)

Triple backticks (` ``` `) immediately follow `=` and the closing ` ``` ` sits on its own line. Everything between them is read verbatim : indentation, blank lines, trailing whitespace. **The closing delimiter determines the left boundary** of the expression; indentation to the right of it is preserved as-is.

```tmdl
measure 'Revenue Won' = ```

		 CALCULATE(
		     SUMX(Opportunities, Opportunities[Value]),
		     FILTER(Opportunities, Opportunities[Status] = "Won")
		 )
		```
	formatString: \$#,0.0;(\$#,0.0);\$#,0.0
```

From `tables/Opportunities.tmdl` (AI Sample). The leading blank line inside the backticks is preserved. The closing ` ``` ` is at two-tab indentation, so the expression content aligns relative to that boundary.

Backticks are also used for long M expressions to preserve exact formatting:

```tmdl
expression OxCGRT_latest = ```
	let
	    Source = Csv.Document(Web.Contents("..."), [...]),
	    ...
	    #"Added Custom9" = Table.AddColumn(...)
	in
	    #"Added Custom9"
	```
```

From `expressions.tmdl` (COVID Bakeoff Sample).

**When backticks are required:** when the expression contains trailing whitespace, blank lines with whitespace, or indentation that would be stripped by normal TMDL rules.

### Expression-Bearing Properties by Type

| Object type | Property | Language |
|---|---|---|
| `measure` | (default) | DAX |
| `calculatedColumn` | (default) | DAX |
| `partition` (type `m`) | `source` | M (Power Query) |
| `partition` (type `calculated`) | `source` | DAX |
| `namedExpression` / `expression` | (default) | M |
| `tablePermission` | (default filter) | DAX |
| `linguisticMetadata` | `content` | JSON |

---

## Descriptions

Object descriptions use **`///` triple-slash** syntax, placed **immediately above** the object declaration (no blank lines between the description and the declaration keyword).

```tmdl
/// Table Description
table Sales

	/// This is the Measure Description
	/// Split across multiple lines when over 80 chars
	measure 'Sales Amount' = SUM(...)
		formatString: #,##0
```

Multi-line descriptions are emitted as multiple `///` lines; the serializer breaks at 80 characters.

---

## Annotations

Annotations are key/value pairs attached to their parent object. They appear after that object's properties and child objects:

```tmdl
column Latitude
	dataType: double
	dataCategory: Latitude
	summarizeBy: none
	sourceColumn: Latitude

	annotation SummarizationSetBy = User
	annotation PBI_FormatHint = {"isGeneralNumber":true}
```

From `tables/Accounts.tmdl` (AI Sample).

Model-level annotations (no indentation):

```tmdl
annotation __PBI_TimeIntelligenceEnabled = 1
annotation PBI_QueryOrder = ["Accounts","Industries","Opportunities",...]
```

From `model.tmdl` (AI Sample).

---

## The `ref` Keyword

### Deterministic Collection Ordering

When objects (tables, cultures, roles) are serialized to individual files, `model.tmdl` uses `ref` statements to declare and preserve their order. This prevents spurious source-control diffs caused by reordering:

```tmdl
model Model
	culture: en-US
	defaultPowerBIDataSourceVersion: powerBI_V3

ref table Accounts
ref table Industries
ref table Opportunities
ref table Owners
ref table 'Opportunity Forecast Adjustment'
ref table Cases
ref table 'Case Calendar'
ref table 'Opportunity Calendar'
...
ref table LocalDateTable_de73616c-e116-4a69-92e1-907ce2a4d5db

ref cultureInfo en-US
```

From `model.tmdl` (AI Sample).

Rules:
- Objects listed in `ref` but with no matching file are silently ignored.
- Objects with a file but no `ref` are appended to the end of the collection.
- Collections with a single item do not emit a `ref`.

### Partial Declaration (`ref table`)

Using `ref table` allows table metadata to be split across files (similar to C# partial classes). Child objects within a `ref table` block are merged into that table's definition from its own file.

---

## File-by-File Reference

### `database.tmdl`

Minimal. Contains only the `database` keyword (no name) and `compatibilityLevel`:

```tmdl
database
	compatibilityLevel: 1567
```

From `database.tmdl` (AI Sample).

### `model.tmdl`

Model-level properties, annotations, and `ref` ordering for tables and cultures:

```tmdl
model Model
	culture: en-US
	defaultPowerBIDataSourceVersion: powerBI_V3
	sourceQueryCulture: en-US
	dataAccessOptions
		legacyRedirects
		returnErrorValuesAsNull

annotation __PBI_TimeIntelligenceEnabled = 1
annotation PBI_QueryOrder = ["Accounts","Industries",...]

ref table Accounts
ref table Industries
...
ref cultureInfo en-US
```

From `model.tmdl` (AI Sample). Note `dataAccessOptions` is a nested object with its own flag-only boolean properties.

### `relationships.tmdl`

All relationships in one file. Each uses a GUID as its name. Properties use dot notation for column references:

```tmdl
relationship c5b245c6-f533-4dbe-be32-ca0932182f37
	isActive: false
	fromColumn: Opportunities.SystemUserSeq
	toColumn: Owners.SystemUserSeq

relationship 31b31781-e688-46e4-87c6-e17c1b83fcac
	joinOnDateBehavior: datePartOnly
	fromColumn: Opportunities.'Opportunity Created On'
	toColumn: LocalDateTable_b0573d09-ef3e-45e2-9f39-8a331c91c6c3.Date
```

From `relationships.tmdl` (AI Sample). See the Non-trivial Cases section for `isActive` and `joinOnDateBehavior`.

### `expressions.tmdl`

All shared named M expressions (Power Query functions / tables). Each can have a `lineageTag`, `queryGroup`, and annotations:

```tmdl
expression Query1 =
		(StartDate as date, EndDate as date, optional Culture as nullable text) as table =>
		    let
		        DayCount = Duration.TotalDays(EndDate - StartDate) + 1,
		        Source = List.Dates(StartDate, DayCount, #duration(1, 0, 0, 0)),
		        ...
		    in
		        InsertWeekofYear
	lineageTag: 2ddf0ecd-db05-43f2-99eb-bfc444d25f5d

	annotation PBI_NavigationStepName = Navigation
	annotation PBI_ResultType = Function
```

From `expressions.tmdl` (AI Sample). Note `lineageTag` and `annotation` sit at the property level (one tab), while the M body is two tabs deep.

Expressions can also carry a `queryGroup` label:

```tmdl
expression 'state population' =
		let
		    Source = Web.BrowserContents("...")
		    ...
		in
		    #"Filtered Rows"
	lineageTag: 2ccd6b6f-...
	queryGroup: Unused
```

From `expressions.tmdl` (COVID Bakeoff Sample).

### `tables/<Table>.tmdl`

One file per table. Contains the table declaration, columns, measures, hierarchies, and partitions.

```tmdl
table 'COVID measures'
	lineageTag: 9f681416-7364-466e-8d62-c4b5606c65be

	measure 'Total confirmed cases' = SUM('COVID'[Daily cases])
		formatString: #,0
		lineageTag: 6703243b-...

	partition 'COVID measures-b4337b49-...' = m
		mode: import
		source =
				let
				    Source = Table.FromRows(...)
				in
				    #"Removed Columns"

	annotation PBI_ResultType = Table
```

From `tables/COVID measures.tmdl` (COVID-19 US Sample). A table with no regular columns : measures only : and a single empty-row M partition.

### `cultures/<locale>.tmdl`

One file per culture. The `linguisticMetadata` object holds a large JSON document as its `content` expression. Because the JSON is treated as a verbatim expression, it is typically backtick-fenced.

---

## Non-trivial Cases

### Calculated Columns

A column with a DAX expression instead of `sourceColumn`. The expression is the column's default property (uses `=`):

```tmdl
column 'Industry Lookup' = LOOKUPVALUE(Industries[Industry], Industries[IndustrySeq], Accounts[IndustrySeq])
	lineageTag: 2e717be5-31d7-4c23-8754-37f4174d134c
	summarizeBy: none
```

Multi-line calculated column from `tables/Opportunities.tmdl` (AI Sample):

```tmdl
column 'Weeks Open' =

		ABS (
		    DATEDIFF (
		        Opportunities[Opportunity Created On],
		        IF (
		            ISBLANK ( Opportunities[CloseDate] ) = TRUE (),
		            TODAY (),
		            Opportunities[CloseDate]
		        ),
		        WEEK
		    )
		)
	formatString: 0
	lineageTag: 306e46c3-...
	summarizeBy: sum
```

Single-line shorthand also works: `column Blank = BLANK()`.

Calculated columns have no `sourceColumn` or `dataType` : the engine infers the type from the DAX result.

### Calculated Partition Source

A partition whose source is a DAX expression (not M) uses `= calculated`:

```tmdl
partition DateTableTemplate_0039983e-...-bd39f04f-... = calculated
	mode: import
	source = Calendar(Date(2015,1,1), Date(2015,1,1))
```

From `tables/DateTableTemplate_0039983e-de71-45fb-bd88-812f61c0ff38.tmdl` (AI Sample). The `source` value here is a single-line DAX expression.

### Column Variations (Date Drill-Through)

DateTime columns linked to auto-date tables carry a `variation` child block. The variation points to the relationship and the default hierarchy by a fully qualified reference:

```tmdl
column 'Opportunity Created On'
	dataType: dateTime
	isHidden
	formatString: Long Date
	lineageTag: cb4340a2-...
	summarizeBy: none
	sourceColumn: Opportunity Created On

	variation Variation
		isDefault
		relationship: 31b31781-e688-46e4-87c6-e17c1b83fcac
		defaultHierarchy: LocalDateTable_b0573d09-ef3e-45e2-9f39-8a331c91c6c3.'Date Hierarchy'
```

From `tables/Opportunities.tmdl` (AI Sample). `isDefault` is a flag-only boolean. `relationship` holds the GUID of the relationship. `defaultHierarchy` uses dot notation: `TableName.'Hierarchy Name'`.

### `sortByColumn`

A column can declare that it should sort by another column's values:

```tmdl
column Month
	dataType: string
	lineageTag: 153dce9c-...
	summarizeBy: none
	sourceColumn: Month
	sortByColumn: MonthNumber
```

From `tables/Date.tmdl` (Human Resources Sample). `MonthNumber` is the name of another column in the same table : no table prefix needed for same-table references.

### Hidden and Private Tables

Auto-generated date tables use two flag-only booleans at the table level:

```tmdl
table DateTableTemplate_0039983e-de71-45fb-bd88-812f61c0ff38
	isHidden
	isPrivate
	lineageTag: eb953d38-...
```

From `tables/DateTableTemplate_0039983e-de71-45fb-bd88-812f61c0ff38.tmdl` (AI Sample). `isPrivate` marks tables that should not be shown to end users or exported.

There is also a table-level `dataCategory` for date tables:

```tmdl
table Date
	lineageTag: 3c20188a-...
	dataCategory: Time
```

From `tables/Date.tmdl` (Human Resources Sample).

### Inactive Relationships

```tmdl
relationship c5b245c6-f533-4dbe-be32-ca0932182f37
	isActive: false
	fromColumn: Opportunities.SystemUserSeq
	toColumn: Owners.SystemUserSeq
```

From `relationships.tmdl` (AI Sample). Active relationships omit `isActive` (it defaults to `true`). Inactive relationships must set it explicitly.

### `joinOnDateBehavior`

Date relationships to auto-date tables can restrict joining to the date part only:

```tmdl
relationship 31b31781-e688-46e4-87c6-e17c1b83fcac
	joinOnDateBehavior: datePartOnly
	fromColumn: Opportunities.'Opportunity Created On'
	toColumn: LocalDateTable_b0573d09-ef3e-45e2-9f39-8a331c91c6c3.Date
```

From `relationships.tmdl` (AI Sample). This prevents time-of-day from affecting relationship matching.

### M Escaped Identifiers (`#"..."`)

Power Query M uses `#"identifier"` syntax for step names that contain spaces or reserved words. These appear verbatim inside M partition sources and named expressions:

```tmdl
source =
		let
		    Source = Excel.Workbook(File.Contents("..."), null, true),
		    AccountTbl_Table = Source{[Item="AccountTbl",Kind="Table"]}[Data],
		    #"Changed Type" = Table.TransformColumnTypes(AccountTbl_Table, {...})
		in
		    #"Changed Type"
```

From `tables/Accounts.tmdl` (AI Sample). The `#"Changed Type"` is a valid M step name with a space. The TMDL lexer treats this token as a single identifier and does not interpret the inner quotes as TMDL string delimiters.

### Format String Escaping

TMDL does not further escape format strings, but some characters are written with a backslash to prevent misinterpretation:

```tmdl
column Value
	formatString: \$#,0;(\$#,0);\$#,0
```

From `tables/Opportunities.tmdl` (AI Sample). The `\$` is a literal dollar sign in the format string. Without the backslash, a bare `$` could be misread.

Three-segment format strings (positive; negative; zero) appear frequently:

```tmdl
	formatString: \$#,0.0;(\$#,0.0);\$#,0.0          ← currency
	formatString: #,0%;-#,0%;#,0%                      ← percentage
	formatString: #,0.###############;(#,0.###############);#,0.###############
```

### Boolean Column Format Strings

A boolean column's format string uses doubled double-quotes to embed string literals:

```tmdl
column 'Decision Maker Identified'
	dataType: boolean
	formatString: """TRUE"";""TRUE"";""FALSE"""
	lineageTag: 70e6bcc8-...
	summarizeBy: none
	sourceColumn: Decision Maker Identified
```

From `tables/Opportunities.tmdl` (AI Sample). The outer double-quotes delimit the TMDL string value; the inner `""` pairs are each a literal `"` character, producing format string: `"TRUE";"TRUE";"FALSE"`.

### `dataCategory` Values

The `dataCategory` property on columns enables geo and semantic features in Power BI:

```tmdl
column Street    → dataCategory: Address
column City      → dataCategory: City
column 'State or Province' → dataCategory: StateOrProvince
column 'Postal Code' → dataCategory: PostalCode
column Country   → dataCategory: Country
column Latitude  → dataCategory: Latitude
column Longitude → dataCategory: Longitude
```

From `tables/Accounts.tmdl` (AI Sample). Date template columns use: `dataCategory: PaddedDateTableDates`, `dataCategory: Years`, `dataCategory: Months`, `dataCategory: Quarters`, `dataCategory: DayOfMonth`.

### `isNameInferred`

A flag-only boolean on columns generated by the auto-date table engine, indicating the column name was not explicitly authored:

```tmdl
column Date
	isHidden
	lineageTag: 9bcc7cc1-...
	dataCategory: PaddedDateTableDates
	summarizeBy: none
	isNameInferred
	sourceColumn: [Date]
```

From `tables/DateTableTemplate_0039983e-de71-45fb-bd88-812f61c0ff38.tmdl` (AI Sample). Note `sourceColumn: [Date]` : the brackets are part of the source column name as emitted by the engine.

### `isKey`

Marks the primary key column of a table:

```tmdl
column Date
	dataType: dateTime
	isKey
	formatString: General Date
	lineageTag: 7c140958-...
	summarizeBy: none
	sourceColumn: Date
```

From `tables/Date.tmdl` (Human Resources Sample). Only one column per table should carry `isKey`.

---

## Parser Implementation Notes

This subpackage implements the TMDL pipeline in `src/pybi/serialization/parsers/tmdl/`:

| File | Role |
|------|------|
| `grammar.py` | Keyword lists, property enums, `quote_name` / `unquote_name` utilities |
| `lexer.py` | Tokenizer : tab-indentation tracking, backtick blocks, `///` descriptions |
| `parser.py` | Token stream → `ObjectDeclaration` AST |
| `transformer.py` | AST → Pydantic models (`Table`, `Column`, `Measure`, …) |
| `loader.py` | `TMDLFolderLoader` (filesystem) and `TMDLPartsLoader` (in-memory `dict[str, str]`) |
| `writer.py` | Pydantic models → TMDL text (`TMDLFolderWriter`, `TMDLPartsWriter`) |
| `exceptions.py` | `TMDLLexerError`, `TMDLParseError`, `TMDLTransformError` with file/line/column context |
