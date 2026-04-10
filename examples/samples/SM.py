SM = {
    "compatibilityLevel": 1567,
    "model": {
        "culture": "en-US",
        "defaultPowerBIDataSourceVersion": "powerBI_V3",
        "expressions": [
            {
                "name": "Query1",
                "expression": ["..."],
                "kind": "m",
                "lineageTag": "2ddf0ecd-db05-43f2-99eb-bfc444d25f5d",
            }
        ],
        "relationships": [
            {
                "name": "89a44a58-1397-4839-a0fe-c46c0c5d890d",
                "fromColumn": "Column1",
                "fromTable": "Table1",
                "toColumn": "Column1",
                "toTable": "Table2",
            }
        ],
        "sourceQueryCulture": "en-US",
        "tables": [
            {
                "name": "Table1",
                "measures": [
                    {
                        "name": "Measure1",
                        "dataType": "int",
                        "expression": "SUM(1)",
                    }
                ],
                "columns": [
                    {
                        "name": "Column1",
                        "dataType": "string",
                        "lineageTag": "3cc966b9-42cc-4fdc-af3e-169dbd480556",
                        "sourceColumn": "Column1",
                        "summarizeBy": "none",
                    },
                    {
                        "name": "Column2",
                        "dataType": "string",
                        "lineageTag": "ed257708-4559-4704-a277-a67e5437a1ca",
                        "sourceColumn": "Column2",
                        "summarizeBy": "none",
                    },
                ],
                "lineageTag": "22d72ed3-5ee0-4ff1-98ec-c82153839a11",
                "partitions": [
                    {
                        "name": "Table1-569e2118-8ef4-4f17-9647-c9b4190bc0c8",
                        "mode": "import",
                        "source": {"expression": ["..."], "type": "m"},
                    }
                ],
            },
            {
                "name": "Table2",
                "columns": [
                    {
                        "name": "Column1",
                        "dataType": "string",
                        "lineageTag": "8b10b876-f44a-4959-846f-ddd0db70c358",
                        "sourceColumn": "Column1",
                        "summarizeBy": "none",
                    },
                    {
                        "name": "Column2",
                        "dataType": "int64",
                        "formatString": "0",
                        "lineageTag": "2b094873-0bc1-4789-8a16-fe25ba521900",
                        "sourceColumn": "Column2",
                        "summarizeBy": "none",
                    },
                ],
                "lineageTag": "46e20580-f584-47f3-9fb6-650aaf55c07d",
                "partitions": [
                    {
                        "name": "Table2-ad0b018f-e5af-41ce-a3f4-c734e885246e",
                        "mode": "import",
                        "source": {"expression": ["..."], "type": "m"},
                    }
                ],
            },
        ],
    },
}
