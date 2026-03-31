import shutil
from poupytempo import SemanticModel
from poupytempo.Utils.utils import read_json

import sys
import os
from loguru import logger
from pathlib import Path

DASHBOARDS_PATH = "C:\\Users\\haw4ca\\Documents\\code\\pbi_workspace"

# create a log file
def setup_logger(
    file_path: str = "logs/app_{time:YYYY-MM-DD}.log",
    level: str = None,
) -> None:
    """Configure Loguru to write to a file (and keep console logs)."""
    level = level or os.getenv("LOG_LEVEL", "INFO")

    # Ensure log directory exists
    Path(file_path).parent.mkdir(parents=True, exist_ok=True)

    # Remove default sink
    logger.remove()

    # Optional: keep console output
    logger.add(sys.stderr, level=level)

    # Main file sink
    logger.add(
        file_path,
        level=level,
        rotation="50 MB",        # or "00:00" for daily, "1 week", etc.
        retention="30 days",     # keep logs for 30 days
        compression="zip",       # compress old logs
        enqueue=True,            # non-blocking, safe for multi-process
        backtrace=True,          # richer tracebacks for exceptions
        diagnose=False,          # set True only during debugging (can leak data)
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<7} | "
               "{process}:{thread.name} | {name}:{function}:{line} | {message}",
    )

setup_logger()

logger.info("Service starting…")

paths = []
# iterate over folders in root_path
for folder in os.listdir(DASHBOARDS_PATH):
    # check if folder is a directory
    if os.path.isdir(os.path.join(DASHBOARDS_PATH, folder)):
        # navigate to folder dashboards
        dashboards_folder = os.path.join(DASHBOARDS_PATH, folder, "dashboards")

        # check if folder dashboards exists
        if os.path.exists(dashboards_folder):
            # iterate over folders in dashboard_folder
            for subfolder in os.listdir(dashboards_folder):
                # check if subfolder is a directory
                if os.path.isdir(os.path.join(dashboards_folder, subfolder)):
                    
                    # navigate to dashboard folder
                    dashboard_path = os.path.join(dashboards_folder, subfolder)
                    if dashboard_path.endswith(".Dataset") or dashboard_path.endswith(".SemanticModel"):
                        
                        definition_path = os.path.join(dashboard_path, "definition")
                        
                        # check if definition folder exists
                        if os.path.exists(definition_path) and os.path.isdir(definition_path):
                            # add to log
                            logger.info(f"Processing folder: {dashboard_path}")
                            
                            # copy definition_path folder
                            copy_definition_path = os.path.join(dashboard_path, "definition_copy")
                            paths.append(definition_path)
                            
                            # check if copy_definition_path exists and delete if it does
                            if os.path.exists(copy_definition_path) and os.path.isdir(copy_definition_path):
                                shutil.rmtree(copy_definition_path)
                            
                            os.system(f'xcopy "{definition_path}" "{copy_definition_path}" /E /I /Y')
                                
                                
for path in paths:
    # compare folder and folder_copy, recursively
    copy_path = path + "_copy"
    logger.info(f"Comparing {path} and {copy_path}")
    
    # use robocopy to compare folders and get files that are different
    os.system(f'robocopy "{path}" "{copy_path}" /E /L /NJH /NJS /FP /NS /NDL /MIR /XX /XF thumbs.db > diff.txt')
    with open("diff.txt", "r") as f:
        differences = f.readlines()
    if differences:
        logger.error(f"Found differences between {path} and {copy_path}:")
        for line in differences:
            logger.error(line.strip())
    else:
        logger.info(f"No differences found between {path} and {copy_path}.")
