from pybi.semanticmodel import SemanticModel


def main():
    path = "./samples/legacy/11.25/ai/Artificial Intelligence Sample.SemanticModel/"
    sm = SemanticModel.read(path)

    assert isinstance(sm.definition.model.tables, list)

    print(f"tables: {len(sm.definition.model.tables)}")
    for t in sm.definition.model.tables:
        print(f"\t{t.name}")


if __name__ == "__main__":
    main()
