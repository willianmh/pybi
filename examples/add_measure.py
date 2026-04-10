import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from samples.SM import SM

from pybi.fabric.fabric import DefinitionPbism, Metadata, Platform
from pybi.semanticmodel.definition import Measure, SemanticModelDefinition
from pybi.semanticmodel.semanticmodel import SemanticModel

sm = SemanticModel(
    item_definition=DefinitionPbism(),
    definition=SemanticModelDefinition.model_validate(SM),
    platform=Platform(
        metadata=Metadata(type="SemanticModel", displayName="Test Model")
    ),
)
print(f"SM loaded, with {len(sm.tables)} table")

table = sm.get_table("Table1")
assert table is not None

print(f"table {table.name}, has {len(table.measures or [])} measures")

new_measure = Measure(
    name="Profit Margin",
    expression="DIVIDE([Profit], [Total Revenue])",
    formatString="0.00%",
)

table.add_measure(new_measure)

print(f"Added '{new_measure.name}' to table '{table.name}'")
print(f"Table now has {len(table.measures or [])} measures")
