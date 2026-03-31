from poupytempo import Dashboard
from poupytempo import SemanticModel


def sort_columns(sm: SemanticModel) -> None:
    """
    Reads the Contoso Dashboard and saves it in a new path

    Usage:
    run from the root of the project

    python examples/read_write/read_write.py
    """

    # sort columns in tables by name
    for table in sm.model.tables:
        table.columns = sorted(table.columns, key=lambda x: x.name)

    sm.save_model()


def copy_measures(source_sm: SemanticModel, target_sm: SemanticModel):
    """
    Copy measures from source to target semantic model
    """

    for source_table in source_sm.model.tables:
        target_table = target_sm.model.get_table_by_name(source_table.name)
        if target_table:
            if source_table.measures:
                target_table.measures = source_table.measures

    target_sm.save_model()


def get_relationship(fromTable, toTable, relationships):
    for relationship in relationships:
        if relationship.fromTable == fromTable and relationship.toTable == toTable:
            return relationship
    return None


def copy_relationships(source_sm: SemanticModel, target_sm: SemanticModel):
    """
    Copy relationships from source to target semantic model
    """

    for source_relationship in source_sm.model.relationships:
        if not source_relationship.toTable.startswith("LocalDateTable"):
            source_fromtable = source_relationship.fromTable
            source_totable = source_relationship.toTable

            rel = get_relationship(source_fromtable, source_totable, target_sm.model.relationships)
            if rel is None:
                target_sm.model.relationships.append(source_relationship)

    target_sm.save_model()


def copy_table_by_name(source_sm: SemanticModel, target_sm: SemanticModel, table_name: str):
    """
    Copy table from source to target semantic model
    """

    source_table = source_sm.model.get_table_by_name(table_name)
    target_table = target_sm.model.get_table_by_name(table_name)

    if source_table and not target_table:
        target_sm.model.tables.append(source_table)

    target_sm.save_model()


if __name__ == "__main__":
    path = "C:\\Users\\haw4ca\\Documents\\code\\pq-dataset\\tmp\\current\\PQ Dataset.Dataset\\model.bim"
    current_sm = SemanticModel.from_model_bim(name="PQ Dataset", model_bin_path=path)

    new_pq_dataset_path = "C:\\Users\\haw4ca\\Documents\\code\\pq-dataset\\report\\PQ Dataset.SemanticModel\\model.bim"
    new_sm = SemanticModel.from_model_bim(name="PQ Dataset", model_bin_path=new_pq_dataset_path)

    # copy_measures(current_sm, new_sm)
    # copy_table_by_name(current_sm, new_sm, "_Measures")
    # copy_table_by_name(current_sm, new_sm, "_Customization")

    copy_relationships(current_sm, new_sm)

    
