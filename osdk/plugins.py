import importlib.util as importlib
from osdk.logger import Logger
from osdk.shell import readdir

logger = Logger("plugins")


def load(path: str):
    logger.log(f"Loading plugin {path}")
    spec = importlib.spec_from_file_location("plugin", path)

    if not spec or not spec.loader:
        logger.error(f"Failed to load plugin {path}")
        return None

    module = importlib.module_from_spec(spec)
    spec.loader.exec_module(module)


def loadAll():
    logger.log("Loading plugins...")
    for files in readdir("meta/plugins"):
        if files.endswith(".py"):
            plugin = load(f"meta/plugins/{files}")

            if plugin:
                print(f"Loaded plugin {plugin.name}")
                plugin.init()
