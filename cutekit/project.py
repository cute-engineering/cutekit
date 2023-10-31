import os

from pathlib import Path


def root() -> str | None:
    cwd = Path.cwd()
    while cwd != Path.root:
        if (cwd / "project.json").is_file():
            return str(cwd)
        cwd = cwd.parent
    return None


def chdir() -> None:
    projectRoot = root()
    if projectRoot is None:
        raise RuntimeError(
            "No project.json found in this directory or any parent directory"
        )

    os.chdir(projectRoot)
