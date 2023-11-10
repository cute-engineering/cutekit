import os
import logging

from cutekit import shell, project, const, context

import importlib.util as importlib

_logger = logging.getLogger(__name__)


def load(path: str):
    _logger.info(f"Loading plugin {path}")
    spec = importlib.spec_from_file_location("plugin", path)

    if not spec or not spec.loader:
        _logger.error(f"Failed to load plugin {path}")
        return None

    module = importlib.module_from_spec(spec)
    spec.loader.exec_module(module)


def loadAll():
    _logger.info("Loading plugins...")

    projectRoot = project.root()

    if projectRoot is None:
        _logger.info("Not in project, skipping plugin loading")
        return

    pj = context.loadProject(projectRoot)
    paths = list(map(lambda e: os.path.join(const.EXTERN_DIR, e), pj.extern.keys())) + [
        "."
    ]

    for dirname in paths:
        pluginDir = os.path.join(projectRoot, dirname, const.META_DIR, "plugins")

        for files in shell.readdir(pluginDir):
            if files.endswith(".py"):
                plugin = load(os.path.join(pluginDir, files))

                if plugin:
                    _logger.info(f"Loaded plugin {plugin.name}")
                    plugin.init()
