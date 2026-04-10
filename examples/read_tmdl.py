from pybi.semanticmodel import SemanticModel

sm = SemanticModel.read("/path/to/My.SemanticModel")

print(f"{len(sm.tables)} tables")
for table in sm.tables:
    n_cols = len(table.columns or [])
    n_measures = len(table.measures or [])
    print(f"  {table.name}  ({n_cols} columns, {n_measures} measures)")
