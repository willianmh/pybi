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
column = sm.get_column("Table1", "Column1")

print(f"Before: {column.name}")
column.name = "Product ID"
print(f"After:  {column.name}")
