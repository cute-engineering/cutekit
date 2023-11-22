from . import cli
from . import const
from . import model
from . import shell

import dataclasses as dt
import json
import logging

from pathlib import Path
from tempfile import TemporaryDirectory

_logger = logging.getLogger(__name__)


@dt.dataclass
class InstallManifest:
    plugins: list[str]
    targets: list[str]


@cli.command("G", "get", "Get a package from a remote repository")
def getCmd(args: cli.Args):
    pkg = args.consumeArg()
    repo = args.consumeOpt(
        "repository", "https://github.com/cute-engineering/cutekit-contrib.git"
    )

    project = model.Project.topmost()

    if project is None:
        raise RuntimeError("Not inside a project")

    if pkg is None:
        raise RuntimeError("No package specified")

    with TemporaryDirectory() as temp:
        try:
            shell.cloneDir(repo, pkg, temp)
        except FileNotFoundError:
            raise RuntimeError(f"Package {pkg} not found")

        pkg_path = Path(temp) / pkg

        with (pkg_path / "install.json").open("r") as f:
            manifest_json = json.load(f)

            [
                manifest_json.setdefault(key, [])
                for key in InstallManifest.__dataclass_fields__.keys()
            ]

            manifest = InstallManifest(**manifest_json)

        plugin_dir = Path(const.META_DIR) / "plugins"
        target_dir = Path(const.TARGETS_DIR)

        plugin_dir.mkdir(parents=True, exist_ok=True)
        target_dir.mkdir(parents=True, exist_ok=True)

        for plugin in manifest.plugins:
            _logger.info(f"Copying {plugin} to {project.id}'s plugins")
            shell.cp(str(pkg_path / plugin), plugin_dir)

        for target in manifest.targets:
            _logger.info(f"Copying {plugin} to {project.id}'s targets")
            shell.cp(str(pkg_path / target), target_dir)
