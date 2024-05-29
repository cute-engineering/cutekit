import logging
import sys
from pathlib import Path

from . import cli, shell, model, const, vt100

import importlib.util as importlib

_logger = logging.getLogger(__name__)


def load(path: Path):
    _logger.info(f"Loading plugin {path}")
    spec = importlib.spec_from_file_location("plugin", path)

    if not spec or not spec.loader:
        _logger.error(f"Failed to load plugin {path}")
        return

    module = importlib.module_from_spec(spec)
    sys.modules["plugin"] = module

    try:
        spec.loader.exec_module(module)
    except Exception as e:
        _logger.error(f"Failed to load plugin {path}: {e}")
        vt100.warning(f"Plugin {path} loading skipped due to error")


def loadAll():
    _logger.info("Loading plugins...")

    project = model.Project.topmost()
    if project is None:
        _logger.info("Not in project, skipping plugin loading")
        return
    paths = list(map(lambda e: const.EXTERN_DIR / e, project.extern.keys())) + ["."]

    for dirname in paths:
        pluginDir = (
            project.dirname() / dirname / const.META_DIR / "plugins"
        ).absolute()
        initFile = pluginDir / "__init__.py"

        if initFile.exists():
            load(initFile)
        else:
            for file in pluginDir.glob("*.py"):
                load(file)


class PluginsArgs:
    safemod: bool = cli.arg(None, "safemode", "Disable plugin loading")


def setup(args: PluginsArgs):
    if args.safemod:
        return
    loadAll()
