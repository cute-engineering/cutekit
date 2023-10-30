import os
from typing import Optional

def root() -> Optional[str]:
    cwd = os.getcwd()
    while cwd != "/" and cwd != os.path.splitdrive(cwd)[0]:
        if os.path.isfile(os.path.join(cwd, "project.json")):
            return cwd
        cwd = os.path.dirname(cwd)
    return None

def chdir() -> None:
    projectRoot = root()
    if projectRoot is None:
        raise RuntimeError(
            "No project.json found in this directory or any parent directory")

    os.chdir(projectRoot)
