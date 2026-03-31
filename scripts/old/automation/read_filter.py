from poupytempo.Utils.utils import read_json, str2dict

import json
import os

DASHBOARDS_PATH = "./report/contoso/"


report_json = read_json("./report/contoso/ContosoSample.Report/report.json")
report_name = "contoso"

filters = []

_report_name = report_name
if "filters" in report_json:
    _level = "report"
    _name = report_name

    _filter_str = report_json["filters"]
    _filter = str2dict(_filter_str)
    if len(_filter) > 0:

        filters.append(
            {
                "level": _level,
                "report_name": _report_name,
                "name": _name,
                "filter": _filter,
            }
        )

if "sections" in report_json:
    for section in report_json["sections"]:
        if "filters" in section:
            _level = "page"
            _name = section["name"]

            _filter_str = section["filters"]
            _filter = str2dict(_filter_str)
            if len(_filter) > 0:

                filters.append(
                    {
                        "level": _level,
                        "report_name": _report_name,
                        "name": _name,
                        "filter": _filter,
                    }
                )

        if "visualContainers" in section:
            for visualContainer in section["visualContainers"]:
                if "filters" in visualContainer:
                    _level = "visual"
                    _name = str2dict(visualContainer["config"])["name"]

                    _filter_str = visualContainer["filters"]
                    _filter = str2dict(_filter_str)

                    if len(_filter) > 0:
                        filters.append(
                            {
                                "level": _level,
                                "report_name": _report_name,
                                "name": _name,
                                "filter": _filter,
                            }
                        )


for filter in filters:
    _report = filter["report_name"]

    # create a directory for the report
    report_dir = os.path.join("./samples/filters/", _report)

    file_name = f"filter_{filter['level']}_{filter['name']}.json"

    # create a directory for the report
    if not os.path.exists(report_dir):
        os.makedirs(report_dir)

    # create a file for the filter
    with open(os.path.join(report_dir, file_name), "w") as file:
        json.dump(filter["filter"], file, indent=2)
