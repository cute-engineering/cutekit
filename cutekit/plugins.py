import os
import logging

from . import shell, model, const

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

    root = model.Project.root()

    if root is None:
        _logger.info("Not in project, skipping plugin loading")
        return

    project = model.Project.at(root)
    paths = list(map(lambda e: const.EXTERN_DIR / e, project.extern.keys())) + ["."]

    for dirname in paths:
        pluginDir = root / dirname / const.META_DIR / "plugins"

        for script in pluginDir.glob("*.py"):
            plugin = load(script)

            if plugin:
                _logger.info(f"Loaded plugin {plugin.name}")
                plugin.init()
