import os
import logging

from cutekit import shell, project

import importlib.util as importlib

logger = logging.getLogger(__name__)

def load(path: str):
    logger.info(f"Loading plugin {path}")
    spec = importlib.spec_from_file_location("plugin", path)

    if not spec or not spec.loader:
        logger.error(f"Failed to load plugin {path}")
        return None

    module = importlib.module_from_spec(spec)
    spec.loader.exec_module(module)


def loadAll():
    logger.info("Loading plugins...")

    projectRoot = project.root()
    if projectRoot is None:
        logger.info("Not in project, skipping plugin loading")
        return
    
    pluginDir = os.path.join(projectRoot, "meta/plugins")

    for files in shell.readdir(pluginDir):
        if files.endswith(".py"):
            plugin = load(os.path.join(pluginDir, files))

            if plugin:
                print(f"Loaded plugin {plugin.name}")
                plugin.init()
