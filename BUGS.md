# Bug Discovery Progress

Bugs discovered by running `scripts/validate_production.py` against production workspace and `samples/` folder.

**Validation run:** 2026-03-31  
**Workspace:** `C:\Users\haw4ca\Documents\code\pbi_workspace`  
**Production totals:** 60 SemanticModels, 63 Reports  

---

## Fixed Bugs (from `samples/` validation)

### BUG-001: `QueryOptions.keepProjectionOrder` required but optional in production
- **Status:** FIXED
- **File:** `src/pybi/report/legacy/legacy_model.py`
- **Error:** `ValidationError: Field required [type=missing] ... keepProjectionOrder`
- **Root cause:** `QueryOptions.keepProjectionOrder` was typed as `bool` (required) but production reports may omit it.
- **Fix:** Changed to `bool | None = None`
- **Affected:** COVID Bakeoff Report (legacy), any report with `QueryOptions` lacking this field.

### BUG-002: `FilterTypeEnum` missing `Passthrough` value
- **Status:** FIXED
- **File:** `src/pybi/expressions/filter.py`
- **Error:** `ValidationError: Input should be 'Categorical', 'Advanced', 'TopN' or 'RelativeDate' [input_value='Passthrough']`
- **Root cause:** `FilterTypeEnum` did not include the `Passthrough` filter type used in production reports.
- **Fix:** Added `PASSTHROUGH = "Passthrough"` to the enum.
- **Affected:** Life expectancy Report (legacy), any report using passthrough filters.

### BUG-003: `PbirStrategy.serialize()` uses wrong attribute name
- **Status:** FIXED
- **File:** `src/pybi/serialization/strategies/pbir.py`
- **Error:** `AttributeError: 'PbirReportDefinition' object has no attribute 'report_metadata'`
- **Root cause:** Serializer accessed `defn.report_metadata` but the field on `PbirReportDefinition` is `defn.report`.
- **Fix:** Changed `defn.report_metadata` → `defn.report`
- **Affected:** All PBIR reports on write (round-trip).

### BUG-004: TMDL writer doesn't protect partition expressions with backticks
- **Status:** FIXED
- **Files:** `src/pybi/serialization/parsers/tmdl/writer.py`
- **Error:** `TMDLLexerError: Unterminated quoted name` on round-trip re-read.
- **Root cause:** Two issues:
  1. `write_partition()` never checked `_needs_backticks()` for source expressions (unlike `write_measure()`), so expressions with special characters were emitted without triple-backtick protection.
  2. `_needs_backticks()` only checked for trailing whitespace and leading spaces, but not for single quotes (`'`) that the TMDL lexer interprets as quoted-name delimiters (e.g., `mov't` in a DAX expression).
- **Fix:** Added backtick wrapping logic to `write_partition()` and added `'` detection to `_needs_backticks()`.
- **Affected:** COVID Bakeoff SemanticModel TMDL round-trip (table "Days with restrictions", expression containing `mov't`).

---

## Open Bugs (from production workspace validation)

### BUG-005: `DataCategory` Literal missing `Uncategorized` and `WebUrl`
- **Status:** OPEN
- **Priority:** HIGH (blocks 31/60 SemanticModel reads)
- **File:** `src/pybi/semanticmodel/types.py`
- **Error:** `ValidationError: Input should be 'Latitude', 'Longitude', ... [input_value='Uncategorized']` and `[input_value='WebUrl']`
- **Root cause:** The `DataCategory` Literal type in `types.py` is missing two values used in production:
  - `Uncategorized` — not in the list at all
  - `WebUrl` — the list has `WebURL` (uppercase L) but production data uses `WebUrl` (lowercase l)
- **Affected models:** 31 SemanticModels fail to read, including: Division Report, Data Flow Monitor (429 errors), Supplier One Pager (360 errors), BVS-Q, Concessions_Report, Digital Heijunka, MQRS, IFL Analysis, Notification View, Q2 Detail View, Quick Links, and others.
- **Suggested fix:** Add `Uncategorized` and `WebUrl` to the `DataCategory` Literal in `types.py`.

### BUG-006: `relatedColumnDetails` receives TMDL string instead of dict
- **Status:** OPEN
- **Priority:** MEDIUM (blocks 4 SemanticModel reads)
- **File:** `src/pybi/semanticmodel/definition.py`, `src/pybi/serialization/parsers/tmdl/transformer.py`
- **Error:** `ValidationError: Input should be a valid dictionary [input_value='             groupByColumn : \'Parameter Fields\'']`
- **Root cause:** `Column.relatedColumnDetails` is typed as `dict | None` but TMDL parsing passes the raw TMDL block text as a string. The transformer does not parse `relatedColumnDetails` sub-properties into a dict.
- **Affected models:** PMQ Management Summary, PUQ Management Summary (both in pmq_workspace — .SemanticModel and .Dataset variants).
- **Suggested fix:** Either:
  - (a) Change field type to `dict | str | None` to accept both formats, or
  - (b) Add TMDL transformer logic to parse `relatedColumnDetails` sub-block into a dict.

### BUG-007: `Relationship.name` is required but can be None in TMDL
- **Status:** OPEN
- **Priority:** MEDIUM (blocks 2 SemanticModel reads)
- **File:** `src/pybi/semanticmodel/definition.py`
- **Error:** `ValidationError: Input should be a valid string [input=None]` at `name` field
- **Root cause:** `Relationship.name` is typed as `str` (required) but some TMDL models have relationships without names (auto-generated UUIDs not present in the TMDL source).
- **Affected models:** PQ Concessions Report, Supplier score card report.
- **Suggested fix:** Change `name: str` to `name: str | None = None` on the `Relationship` model.

---

## Production Validation Summary

| Category | Total | Passed | Failed | Notes |
|---|---|---|---|---|
| SemanticModel (read) | 60 | 29 | 31 | All failures are BUG-005/006/007 |
| SemanticModel (round-trip) | 29 | 29 | 0 | All reads that succeed also round-trip |
| Report (read) | 63 | 63 | 0 | All reports read successfully |
| Report (round-trip) | 63 | 63 | 0 | All reports round-trip successfully |

### Elements loaded from passing models
- **SemanticModel:** 301 tables, 1901 columns, 275 measures, 191 relationships, 88 expressions, 301 partitions
- **Report:** (all 63 pass)

### Failure breakdown by root cause
| Bug | Affected models | Error type |
|---|---|---|
| BUG-005 (`DataCategory`) | 31 models | Missing `Uncategorized` (most), missing `WebUrl` (some) |
| BUG-006 (`relatedColumnDetails`) | 4 models | TMDL string not parsed to dict |
| BUG-007 (`Relationship.name`) | 2 models | Name is None but required |

*Note: Some models have multiple bugs (e.g., DataCategory + relatedColumnDetails), but the first validation error prevents counting subsequent ones. After fixing BUG-005, additional instances of BUG-006/007 may surface.*
