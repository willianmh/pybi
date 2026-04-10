import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from samples.SM import SM

from pybi.fabric.fabric import DefinitionPbism, Metadata, Platform
from pybi.semanticmodel.definition import SemanticModelDefinition
from pybi.semanticmodel.semanticmodel import SemanticModel

sm = SemanticModel(
    item_definition=DefinitionPbism(),
    definition=SemanticModelDefinition.model_validate(SM),
    platform=Platform(
        metadata=Metadata(type="SemanticModel", displayName="Test Model")
    ),
)
print(f"{len(sm.tables)} tables")
for table in sm.tables:
    n_cols = len(table.columns or [])
    n_measures = len(table.measures or [])
    print(f"  {table.name}  ({n_cols} columns, {n_measures} measures)")
