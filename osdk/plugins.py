import os
import logging

import importlib.util as importlib
from osdk.shell import readdir

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
    for files in readdir(os.path.join("meta", "plugins")):
        if files.endswith(".py"):
            plugin = load(os.path.join("meta", "plugins", files))

            if plugin:
                print(f"Loaded plugin {plugin.name}")
                plugin.init()
