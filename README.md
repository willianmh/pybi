# pybi

[![CodSpeed](https://img.shields.io/endpoint?url=https://codspeed.io/badge.json)](https://codspeed.io/willianmh/pybi?utm_source=badge)

A Python framework for programmatically reading, writing, and manipulating Power BI projects.

**Requirements:** Python ≥ 3.14 · Power BI file saved as `.pbip` ([docs](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-overview))

## Installation

```bash
pip install pybi
# or
uv add pybi
```

## Usage

### PowerBI

```python
from pybi import PowerBI

# Load a full .pbip project (auto-resolves report and semantic model)
pbi = PowerBI.from_pbip("/path/to/My.pbip")

sm = pbi.semantic_model
report = pbi.report
```

### SemanticModel

```python
from pybi.semanticmodel import SemanticModel

# Read (auto-detects TMDL or model.bim)
sm = SemanticModel.read("/path/to/My.SemanticModel")

# Browse tables, columns, and measures
for table in sm.tables:
    print(table.name, [c.name for c in table.columns])

measure = sm.get_measure("Total Sales")
print(measure.expression)
```

```python
# Modify and save
table = sm.get_table("Sales")
table.name = "Orders"

sm.save()  # write back to original path
```

### Report

```python
from pybi.report import Report

# Read (auto-detects PBIR or legacy report.json)
report = Report.read("/path/to/My.Report")

# Browse pages and visuals
for page in report.pages:
    print(page.display_name, len(page.visuals))
```

```python
# Look up a specific page
page = report.get_page("Overview")
for visual in page.visuals:
    print(visual)
```

## Supported Formats

| Artifact       | Format    | Description                       |
| -------------- | --------- | --------------------------------- |
| Semantic Model | TMDL      | Folder of `.tmdl` files (default) |
| Semantic Model | model.bim | Single JSON file (legacy)         |
| Report         | PBIR      | Folder of versioned JSON files    |
| Report         | legacy    | Single `report.json` file         |

Format is auto-detected on read. To write in a specific format:

```python
from pybi.semanticmodel.types import SemanticModelFormat

sm.write("/output/path", format=SemanticModelFormat.TMDL)
```
