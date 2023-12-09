import logging
import os
import sys

from . import shell, model, const, cli

import importlib.util as importlib

_logger = logging.getLogger(__name__)


def load(path: str):
    _logger.info(f"Loading plugin {path}")
    spec = importlib.spec_from_file_location("plugin", path)

    if not spec or not spec.loader:
        _logger.error(f"Failed to load plugin {path}")
        return None

    module = importlib.module_from_spec(spec)
    sys.modules["plugin"] = module
    spec.loader.exec_module(module)


def loadAll():
    _logger.info("Loading plugins...")

    project = model.Project.topmost()
    if project is None:
        _logger.info("Not in project, skipping plugin loading")
        return
    paths = list(
        map(lambda e: os.path.join(const.EXTERN_DIR, e), project.extern.keys())
    ) + ["."]

    for dirname in paths:
        pluginDir = os.path.join(project.dirname(), dirname, const.META_DIR, "plugins")
        initFile = os.path.join(pluginDir, "__init__.py")

        if os.path.isfile(initFile):
            load(initFile)
        else:
            for files in shell.readdir(pluginDir):
                if files.endswith(".py"):
                    load(os.path.join(pluginDir, files))


def setup(args: cli.Args):
    if not bool(args.consumeOpt("safemode", False)):
        loadAll()
