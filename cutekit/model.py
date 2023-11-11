import os
import logging


from enum import Enum
from typing import Any, Type, cast
from pathlib import Path
from dataclasses_json import DataClassJsonMixin, config
from dataclasses import dataclass, field

from . import jexpr, compat, utils

_logger = logging.getLogger(__name__)

Props = dict[str, Any]


class Kind(Enum):
    UNKNOWN = "unknown"
    PROJECT = "project"
    TARGET = "target"
    LIB = "lib"
    EXE = "exe"


@dataclass
class Manifest(DataClassJsonMixin):
    id: str
    type: Kind = field(default=Kind.UNKNOWN)
    path: str = field(default="")

    @staticmethod
    def parse(path: Path, data: dict[str, Any]) -> "Manifest":
        compat.ensureSupportedManifest(data, path)
        kind = Kind(data["type"])
        del data["$schema"]
        obj = KINDS[kind].from_dict(data)
        obj.path = str(path)
        return obj

    @staticmethod
    def load(path: Path) -> "Manifest":
        return Manifest.parse(path, jexpr.evalRead(path))

    def dirname(self) -> str:
        return os.path.dirname(self.path)

    def ensureType(self, t: Type[utils.T]) -> utils.T:
        if not isinstance(self, t):
            raise RuntimeError(
                f"{self.path} should be a {type.__name__} manifest but is a {self.__class__.__name__} manifest"
            )
        return cast(utils.T, self)


@dataclass
class Extern(DataClassJsonMixin):
    git: str
    tag: str


@dataclass
class Project(Manifest):
    description: str = field(default="(No description)")
    extern: dict[str, Extern] = field(default_factory=dict)

    @staticmethod
    def root() -> str | None:
        cwd = Path.cwd()
        while str(cwd) != cwd.root:
            if (cwd / "project.json").is_file():
                return str(cwd)
            cwd = cwd.parent
        return None

    @staticmethod
    def chdir() -> None:
        path = Project.root()
        if path is None:
            raise RuntimeError(
                "No project.json found in this directory or any parent directory"
            )
        os.chdir(path)


@dataclass
class Tool(DataClassJsonMixin):
    cmd: str = field(default="")
    args: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)


Tools = dict[str, Tool]


@dataclass
class Target(Manifest):
    props: Props = field(default_factory=dict)
    tools: Tools = field(default_factory=dict)
    routing: dict[str, str] = field(default_factory=dict)

    def route(self, componentSpec: str):
        return (
            self.routing[componentSpec]
            if componentSpec in self.routing
            else componentSpec
        )

    def cdefs(self) -> list[str]:
        defines: list[str] = []

        def sanatize(s: str) -> str:
            return s.lower().replace(" ", "_").replace("-", "_").replace(".", "_")

        for key in self.props:
            prop = self.props[key]
            propStr = str(prop)
            if isinstance(prop, bool):
                if prop:
                    defines += [f"-D__ck_{sanatize(key)}__"]
            else:
                defines += [f"-D__ck_{sanatize(key)}_{sanatize(propStr)}__"]
                defines += [f"-D__ck_{sanatize(key)}_value={propStr}"]

        return defines


@dataclass
class Component(Manifest):
    decription: str = field(default="(No description)")
    props: Props = field(default_factory=dict)
    tools: Tools = field(default_factory=dict)
    enableIf: dict[str, list[Any]] = field(default_factory=dict)
    requires: list[str] = field(default_factory=list)
    provides: list[str] = field(default_factory=list)
    subdirs: list[str] = field(default_factory=list)

    def isEnabled(self, target: Target) -> tuple[bool, str]:
        for k, v in self.enableIf.items():
            if k not in target.props:
                _logger.info(f"Component {self.id} disabled by missing {k} in target")
                return False, f"Missing props '{k}' in target"

            if target.props[k] not in v:
                vStrs = [f"'{str(x)}'" for x in v]
                _logger.info(
                    f"Component {self.id} disabled by {k}={target.props[k]} not in {v}"
                )
                return (
                    False,
                    f"Props missmatch for '{k}': Got '{target.props[k]}' but expected {', '.join(vStrs)}",
                )

        return True, ""


KINDS: dict[Kind, Type[Manifest]] = {
    Kind.PROJECT: Project,
    Kind.TARGET: Target,
    Kind.LIB: Component,
    Kind.EXE: Component,
}
