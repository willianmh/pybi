# pybi

A Python framework for programmatically reading, writing, and manipulating Power BI projects.

**Requirements:** Python ≥ 3.14 · Power BI file saved as `.pbip` ([docs](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-overview))

## Installation

```bash
pip install pybi
# or
uv add pybi
```

## Quick Start

```python
from pybi.semanticmodel.semanticmodel import SemanticModel

# Read a semantic model (auto-detects TMDL or model.bim)
sm = SemanticModel.read("/path/to/My.SemanticModel")

# Inspect the model
for table in sm.definition.model.tables:
    print(table.name)

# Modify and write back
sm.definition.model.tables[0].name = "Renamed"
sm.write("/path/to/My.SemanticModel")
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
