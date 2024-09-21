import logging
import os
import sys

from . import cli, model, const, vt100, shell
from pathlib import Path

import importlib.util as importlib

_logger = logging.getLogger(__name__)


def load(path: str):
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
        vt100.warning(f"Plugin {path} loading skipped due to: {e}")


def loadAll():
    _logger.info("Loading plugins...")

    project = model.Project.topmost()
    paths = list(Path(const.GLOBAL_PLUGIN_DIR).glob("*/"))

    if project:
        paths += list(
            map(
                lambda e: Path(project.dirname()) / e / const.META_DIR / "plugins",
                project.extern.keys(),
            )
        ) + [Path(project.dirname()) / const.META_DIR / "plugins"]

    for path in paths:
        if (path / "__init__.py").exists():
            load(str(path / "__init__.py"))
        else:
            map(lambda p: load(str(p)), path.glob("*.py"))


class PluginsArgs:
    safemod: bool = cli.arg(None, "safemode", "Disable plugin loading")


def setup(args: PluginsArgs):
    if args.safemod:
        return
    loadAll()


@cli.command("P", "plugins", "Manage plugins")
def _():
    pass


class PluginsInstallArgs:
    url: str = cli.arg(None, "url", "Git url of the plugin")
    acknowledge: bool = cli.arg(
        None, "acknowledge-risk", "Acknowledge the risk of installing a plugin"
    )


@cli.command("i", "plugins/install", "Install a plugin")
def _(args: PluginsInstallArgs):
    project = model.Project.topmost()

    header = """Please read the following information carefully before proceeding:
- Plugins are not sandboxed and can execute arbitrary code
- Only install plugins from trusted sources
- Cutekit is unable to verify the integrity, security, and safety of plugins

Proceed with caution and at your own risk.
Do you want to continue? [y/N] """

    if not args.url and not project:
        raise RuntimeError("No plugin source was specified")

    choice = input(header)

    if choice.lower() == "y":
        if args.url:
            shell.cloneDir(
                args.url,
                "meta/plugins",
                os.path.join(const.GLOBAL_PLUGIN_DIR, args.url.split("/")[-1]),
            )
        elif project:
            shell.cpTree(
                str(Path(project.dirname()) / "meta" / "plugins"),
                os.path.join(const.GLOBAL_PLUGIN_DIR, project.id),
            )

        if (
            Path(const.GLOBAL_PLUGIN_DIR) / args.url.split("/")[-1] / "requirements.txt"
        ).exists():
            shell.exec(
                sys.executable,
                "-m",
                "pip",
                "install",
                "-r",
                str(
                    Path(const.GLOBAL_PLUGIN_DIR)
                    / args.url.split("/")[-1]
                    / "requirements.txt"
                ),
            )
    else:
        raise RuntimeError("Plugin installation aborted")
