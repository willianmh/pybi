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

print(f"{len(sm.measures)} measures across {len(sm.tables)} tables\n")
for table, measure in sm.measures:
    expr = measure.expression.value if measure.expression else "(none)"
    print(f"[{table.name}] {measure.name}")
    print(f"  {expr}\n")
