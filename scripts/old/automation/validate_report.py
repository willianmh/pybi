import json
from poupytempo import Report
from poupytempo.Utils.utils import read_json, str2dict

import os


def output(pydantic_model_obj : str, report_obj: str, attr, id):
    if len(str(pydantic_model_obj)) < 300:
        print(f'pydantic model: {pydantic_model_obj}')
        print(f'report        : {report_obj}')
    else:
        # create folder id
        os.makedirs(f'samples/validation/{id}', exist_ok=True)
        # serialize the model and save to a file to visualize the difference
        with open(f'samples/validation/{id}/{attr}_{id}_pydantic_model.json', 'w') as f:
            json.dump(pydantic_model_obj, f, indent=2)

        with open(f'samples/validation/{id}/{attr}_{id}_report.json', 'w') as f:
            json.dump(report_obj, f, indent=2)


root_path = "C:\\Users\\haw4ca\\Documents\\code\\pbi_workspace"


# iterate over folders in root_path
def get_reports(root_path):
    reports = {}
    for folder in os.listdir(root_path):
        # check if folder is a directory
        if os.path.isdir(os.path.join(root_path, folder)):
            # navigate to folder dashboards
            dashboards_folder = os.path.join(root_path, folder, "dashboards")

            # iterate over folder in dashboard_folder
            for subfolder in os.listdir(dashboards_folder):
                # check if dashboard is a directory
                if os.path.isdir(os.path.join(dashboards_folder, subfolder)):
                    # navigate to dashboard folder
                    dashboard_path = os.path.join(dashboards_folder, subfolder)
                    if dashboard_path.endswith(".Report"):
                        report_file = os.path.join(dashboard_path, "report.json")

                        try:
                            read_json(report_file)
                            reports[subfolder.split(".")[0]] = report_file
                        except Exception as e:
                            print(e)
                            continue
    return reports


# delete folder validation
os.system("rmdir /s /q samples\\validation")

reports = get_reports(root_path)


for report_name, report_file in reports.items():
    print(f'Validating {report_name}...')
    # load report
    report_json = read_json(reports[report_name])
    report_model = Report(**report_json)

    # check report config

    # convert to dict
    report_config_dict = str2dict(report_json["config"])

    # iterate over attributes
    for attr in report_config_dict.keys():
        # check if report_model has the attribute
        if not hasattr(report_model.config, attr):
            print(f'Attribute {attr} is not in the report model')

        else:
            # check the bookmarks
            if attr == "bookmarks":
                if report_name == "46944557-dfd1-44f1-9a52-a97f002e27b9":
                    print("stop")
                bookmark_dict = report_config_dict[attr]
                for i in range(len(report_model.config.bookmarks)):
                    if "children" in bookmark_dict[i].keys():
                        for j in range(len(report_model.config.bookmarks[i].children)):
                            
                            # iterate over attributes of children
                            for child_attr in bookmark_dict[i]["children"][j].keys():
                                if not hasattr(report_model.config.bookmarks[i].children[j], child_attr):
                                    print(f'Attribute {child_attr} is not in the report model')
                                else:
                                    # check if attribute implements method model_dump
                                    bookmark_model_attr = None
                                    if hasattr(report_model.config.bookmarks[i].children[j].__getattribute__(child_attr), "model_dump"):
                                        bookmark_model_attr = report_model.config.bookmarks[i].children[j].__getattribute__(child_attr).model_dump(mode="json",exclude_none=True)
                                    else:
                                        bookmark_model_attr = report_model.config.bookmarks[i].children[j].__getattribute__(child_attr)

                                    if bookmark_model_attr != bookmark_dict[i]["children"][j][child_attr]:
                                        print(f'Attribute {child_attr} is not valid')
                                        output(
                                            bookmark_model_attr,
                                            bookmark_dict[i]["children"][j][child_attr],
                                            child_attr,
                                            f'{report_name}_bookmark_{i}'
                                        )

                            # check bookmark
                            if report_model.config.bookmarks[i].children[j].model_dump(mode="json",exclude_none=True) != bookmark_dict[i]["children"][j]:
                                print(f"Bookmark is not valid")
                                output(
                                    report_model.config.bookmarks[i].children[j].model_dump(mode="json",exclude_none=True),
                                    bookmark_dict[i]["children"][j],
                                    "bookmark",
                                    f'{report_name}_bookmark_{i}'
                                )

                    else:
                        # iterate over attributes of bookmark
                        for child_attr in bookmark_dict[i].keys():
                            if not hasattr(report_model.config.bookmarks[i], child_attr):
                                print(f'Attribute {child_attr} is not in the report model')
                            else:
                                # check if attribute implements method model_dump
                                bookmark_model_attr = None
                                if hasattr(report_model.config.bookmarks[i].__getattribute__(child_attr), "model_dump"):
                                    bookmark_model_attr = report_model.config.bookmarks[i].__getattribute__(child_attr).model_dump(mode="json",exclude_none=True)
                                else:
                                    bookmark_model_attr = report_model.config.bookmarks[i].__getattribute__(child_attr)

                                if bookmark_model_attr != bookmark_dict[i][child_attr]:
                                    print(f'Attribute {child_attr} is not valid')
                                    output(
                                        bookmark_model_attr,
                                        bookmark_dict[i][child_attr],
                                        child_attr,
                                        f'{report_name}_bookmark_{i}'
                                    )

                        if report_model.config.bookmarks[i].model_dump(mode="json",exclude_none=True) != bookmark_dict[i]:
                            print(
                                report_model.config.bookmarks[i]
                                .model_dump(mode="json",exclude_none=True)
                                .keys()
                            )
                            print(bookmark_dict[i].keys())
                            print("Bookmark is not valid")
            else:
                if hasattr(report_model.config.__getattribute__(attr), "model_dump"):
                    if report_model.config.__getattribute__(attr).model_dump(mode="json",exclude_none=True) != report_config_dict[attr]:
                        print(f'Attribute {attr} is not valid')
                        # check size before printing
                        output(
                            report_model.config.__getattribute__(attr).model_dump(mode="json",exclude_none=True), 
                            report_config_dict[attr],
                            attr=attr,
                            id=report_name
                        )
                else:
                    if isinstance(report_model.config.__getattribute__(attr), list):
                        for i in range(len(report_model.config.__getattribute__(attr))):
                            if report_model.config.__getattribute__(attr)[i].model_dump(mode="json",exclude_none=True)  != report_config_dict[attr][i]:
                                print(f'Attribute {attr} in list is not valid')
                                # check size before printing
                                output(
                                    report_model.config.__getattribute__(attr)[i].model_dump(mode="json",exclude_none=True) , 
                                    report_config_dict[attr][i],
                                    attr=attr,
                                    id=report_name
                                )
                        
                    elif report_model.config.__getattribute__(attr) != report_config_dict[attr]:
                        print(f'Dict Attribute {attr} is not valid')
                        # check size before printing
                        output(
                            report_model.config.__getattribute__(attr), 
                            report_config_dict[attr],
                            attr=attr,
                            id=report_name
                        )
    
    # check sections
    if report_model.sections:
        if len(report_model.sections) != len(report_json["sections"]):
            print("Sections are not the same size")

        for s_model, s in zip(report_model.sections, report_json["sections"]):
            if s_model.model_dump(mode="json",exclude_none=True) != s:
                print("Section is not valid")
                output(
                    s_model.model_dump(mode="json",exclude_none=True),
                    s,
                    "section",
                    s["name"])

                # check each attribute in section
                for attr in s_model.model_dump(mode="json",exclude_none=True).keys():
                    s_attr = s[attr]

                    # check section config
                    if attr == "config":
                        s_attr = str2dict(s[attr])
                        # check objects
                        
                        # check obj
                        if s_model.__getattribute__(attr).model_dump(mode="json",exclude_none=True) != s_attr:
                            print(f'according to attribute {attr}')
                            output(
                                s_model.__getattribute__(attr).model_dump(mode="json",exclude_none=True),
                                s_attr,
                                attr,
                                s["name"]
                            )
                        # check serialization
                        if s_model.model_dump(mode="json",exclude_none=True)[attr] != s[attr]:
                            print("difference to serialize section config")
                            output(
                                s_model.model_dump(mode="json",exclude_none=True)[attr],
                                s[attr],
                                f'{attr}_str',
                                s["name"]
                            )
                    
                    # check section filters
                    elif attr == "filters":
                        s_attr = str2dict(s[attr])
                        # check each filter obj
                        for f_model, f in zip(s_model.__getattribute__(attr), s_attr):
                            if f_model.model_dump(mode="json",exclude_none=True) != f:
                                print(f'according to attribute {attr}')
                                output(
                                    f_model.model_dump(mode="json",exclude_none=True),
                                    f,
                                    "filter",
                                    f'{s["name"]}_{f["name"]}'
                                )

                        # check serialization of list of filters
                        if s_model.model_dump(mode="json",exclude_none=True)[attr] != s[attr]:
                            print("difference to serialize section filters")
                            output(
                                    s_model.model_dump(mode="json",exclude_none=True)[attr],
                                    s[attr],
                                    "filter_str",
                                    f'{s["name"]}_{f["name"]}'
                                )
                    
                    # check Visual Containers
                    elif attr == "visualContainers":
                        if len(s_model.__getattribute__(attr)) != len(s[attr]):
                            print("Visual Containers are not the same size")

                        for vc_model, vc in zip(s_model.__getattribute__(attr), s[attr]):
                            # check visual container config
                            visual_container_config = str2dict(vc["config"])

                            if vc_model.config.model_dump(mode="json",exclude_none=True) != visual_container_config:
                                print(f'config of visual container is not valid')
                                output(
                                    vc_model.config.model_dump(mode="json",exclude_none=True), 
                                    visual_container_config,
                                    "visualContainers",
                                    visual_container_config["name"]
                                    )
                            # check visual container serialization
                            if vc_model.model_dump(mode="json",exclude_none=True)["config"] != vc["config"]:
                                print("difference to serialize section config")
                                output(
                                    str2dict(vc_model.model_dump(mode="json",exclude_none=True)["config"]),
                                    str2dict(vc["config"]),
                                    'visualContainers_str',
                                    visual_container_config["name"]
                                )

                            # check visual container filters
                            if vc_model.filters:
                                visual_container_filters = str2dict(vc["filters"])
                                for f_model, f in zip(vc_model.filters, visual_container_filters):
                                    if f_model.model_dump(mode="json",exclude_none=True) != f:
                                        print(f'filter of visual container is not valid')
                                        output(
                                            f_model.model_dump(mode="json",exclude_none=True),
                                            f,
                                            "filter_visual_container",
                                            f'{visual_container_config["name"]}_{f["name"]}'
                                        )

                            # check serialization of list of filters
                                if str(vc_model.model_dump(mode="json",exclude_none=True)["filters"]) != vc["filters"]:
                                    print("difference to serialize visualcontainers filters")
                                    output(
                                            str(vc_model.filters.model_dump(mode="json",exclude_none=True)),
                                            vc["filters"],
                                            "filter_str",
                                            f'{s["name"]}_{f["name"]}'
                                        )
                                
                    else:
                        if s_model.__getattribute__(attr) != s[attr]:
                            print(f'according to attribute {attr}')
                            output(
                                s_model.__getattribute__(attr),
                                s[attr],
                                attr,
                                s["name"]
                            )
