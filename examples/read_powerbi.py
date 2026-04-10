from pybi import PowerBI

pbi = PowerBI.from_pbip("/path/to/My.pbip")

# Semantic model
sm = pbi.semantic_model
print(f"{len(sm.tables)} tables")
for table in sm.tables:
    print(f"  {table.name}")

# Report
report = pbi.report
print(f"\n{len(report.pages)} pages")
for page in report.pages:
    display_name = getattr(page.page, "displayName", page.page.name)
    print(f"  {display_name}  ({len(page.visuals)} visuals)")
