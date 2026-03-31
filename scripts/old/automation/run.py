import os
from poupytempo.Models.filter_model import Filter
from poupytempo.Utils.utils import read_json


sample_path = "samples/filters"

# iterate over folders in sample_path
for folder in os.listdir(sample_path):
    folder_path = os.path.join(sample_path, folder)
    if os.path.isdir(folder_path):
        # iterate over files in folder
        for file in os.listdir(folder_path):
            file_path = os.path.join(folder_path, file)
            if os.path.isfile(file_path):
                # read filters from file
                filters = read_json(file_path)

                # check if filter has name
                for idx, filter in enumerate(filters):
                    # if not filter.get("name"):
                    #     print(f"Filter idx {idx} in {file_path} does not have a name.")

                    f = Filter(**filter)

                    source_fields = f.source_fields()
                    if not source_fields:
                        print(f"Filter idx {idx} in {file_path} does not have source fields.")

                    if len(source_fields) > 1:
                        print(f"Filter idx {idx} in {file_path} has more than one source field.")

                    for field in source_fields:
                        # check if field has Entity, Property and Type
                        if not field.get("Entity"):
                            print(f"Filter idx {idx} in {file_path} does not have Entity.")

                        if not field.get("Property"):
                            print(f"Filter idx {idx} in {file_path} does not have Property.")

                        if not field.get("Type"):
                            print(f"Filter idx {idx} in {file_path} does not have Type.")
