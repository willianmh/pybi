"""
This script validates the code framework against production files.

It visits a folder with working cases, find the Semantic Model for each project and loads its json.


With the json object, it will validate its blocks against the pydantic model SemanticModel.
"""

from poupytempo.semanticmodel.models import SemanticModelDefinition
from poupytempo.utils.utils import read_json

import os

DASHBOARDS_PATH = "C:\\Users\\haw4ca\\Documents\\code\\pbi_workspace"

reports = {}
# iterate over folders in root_path
for folder in os.listdir(DASHBOARDS_PATH):
    # check if folder is a directory
    if os.path.isdir(os.path.join(DASHBOARDS_PATH, folder)):
        # navigate to folder dashboards
        dashboards_folder = os.path.join(DASHBOARDS_PATH, folder, "dashboards")

        # check if folder dashboards exists
        if os.path.exists(dashboards_folder):
            # iterate over folder in dashboard_folder
            for subfolder in os.listdir(dashboards_folder):

                # check if dashboard is a directory
                if os.path.isdir(os.path.join(dashboards_folder, subfolder)):

                    # navigate to dashboard folder
                    dashboard_path = os.path.join(dashboards_folder, subfolder)
                    if dashboard_path.endswith(".Dataset") or dashboard_path.endswith(
                        ".SemanticModel"
                    ):
                        report_file = os.path.join(dashboard_path, "model.bim")

                        try:
                            read_json(report_file)
                            reports[subfolder.split(".")[0]] = report_file
                        except Exception as e:
                            print(e)
                            continue

for report_name, report_file in reports.items():
    report_json = read_json(reports[report_name])

    report_name_formatted = report_name.replace(" ", "_").lower()
    print("===================================================")
    print(f"Validating {report_name_formatted}...")

    try:
        dataset_model = SemanticModelDefinition(**report_json)

        step = "tables"
        for i in range(len(dataset_model.model.tables)):
            step = "columns"
            if dataset_model.model.tables[i].columns:
                for j in range(len(dataset_model.model.tables[i].columns)):
                    if str(
                        dataset_model.model.tables[i]
                        .columns[j]
                        .model_dump(exclude_none=True)
                    ) != str(report_json["model"]["tables"][i]["columns"][j]):
                        print(
                            dataset_model.model.tables[i]
                            .columns[j]
                            .model_dump(exclude_none=True)
                            .keys()
                        )
                        print(report_json["model"]["tables"][i]["columns"][j].keys())
                        print("Column is not valid")

            step = "measures"
            if dataset_model.model.tables[i].measures:
                for j in range(len(dataset_model.model.tables[i].measures)):

                    if str(
                        dataset_model.model.tables[i]
                        .measures[j]
                        .model_dump(exclude_none=True)
                    ) != str(report_json["model"]["tables"][i]["measures"][j]):
                        print(
                            dataset_model.model.tables[i]
                            .measures[j]
                            .model_dump(exclude_none=True)
                            .keys()
                        )
                        print(report_json["model"]["tables"][i]["measures"][j].keys())
                        print("Measure is not valid")

            step = "partitions"
            for j in range(len(dataset_model.model.tables[i].partitions)):
                if str(
                    dataset_model.model.tables[i]
                    .partitions[j]
                    .model_dump(exclude_none=True)
                ) != str(report_json["model"]["tables"][i]["partitions"][j]):
                    print(
                        dataset_model.model.tables[i]
                        .partitions[j]
                        .model_dump(exclude_none=True)
                        .keys()
                    )
                    print(report_json["model"]["tables"][i]["partitions"][j].keys())
                    print("Partition is not valid")

            if str(dataset_model.model.tables[i].model_dump(exclude_none=True)) != str(
                report_json["model"]["tables"][i]
            ):
                print(
                    dataset_model.model.tables[i].model_dump(exclude_none=True).keys()
                )
                print(report_json["model"]["tables"][i].keys())
                print("Table is not valid")

        step = "relationships"
        if dataset_model.model.relationships:
            for i in range(len(dataset_model.model.relationships)):
                if str(
                    dataset_model.model.relationships[i].model_dump(exclude_none=True)
                ) != str(report_json["model"]["relationships"][i]):
                    print(
                        dataset_model.model.relationships[i]
                        .model_dump(exclude_none=True)
                        .keys()
                    )
                    print(report_json["model"]["relationships"][i].keys())
                    print("relationships is not valid")

        step = "expressions"
        if dataset_model.model.expressions:
            for i in range(len(dataset_model.model.expressions)):
                if str(
                    dataset_model.model.expressions[i].model_dump(exclude_none=True)
                ) != str(report_json["model"]["expressions"][i]):
                    print(
                        dataset_model.model.expressions[i]
                        .model_dump(exclude_none=True)
                        .keys()
                    )
                    print(report_json["model"]["expressions"][i].keys())
                    print("expressions is not valid")

        if str(dataset_model.model.model_dump(exclude_none=True)) != str(
            report_json["model"]
        ):
            print(dataset_model.model.model_dump(exclude_none=True).keys())
            print(report_json["model"].keys())
            print("Model is not valid")

        if str(dataset_model.model_dump(exclude_none=True)) != str(report_json):
            print(dataset_model.model_dump(exclude_none=True).keys())
            print(report_json.keys())
            print(f"Dataset {report_file} is not valid")

        print(f"Dataset {report_file} finished validation")

    except Exception as e:
        print(f"Dataset {report_file} is not valid")
        print(e)
        continue
