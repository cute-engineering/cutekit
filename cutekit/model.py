import os
from enum import Enum
from typing import Any
import logging

from cutekit.jexpr import Json


_logger = logging.getLogger(__name__)

Props = dict[str, Any]


class Type(Enum):
    UNKNOWN = "unknown"
    PROJECT = "project"
    TARGET = "target"
    LIB = "lib"
    EXE = "exe"


class Manifest:
    id: str = ""
    type: Type = Type.UNKNOWN
    path: str = ""

    def __init__(
        self, json: Json = None, path: str = "", strict: bool = True, **kwargs: Any
    ):
        if json is not None:
            if "id" not in json:
                raise RuntimeError("Missing id")

            self.id = json["id"]

            if "type" not in json and strict:
                raise RuntimeError("Missing type")

            self.type = Type(json["type"])

            self.path = path
        elif strict:
            raise RuntimeError("Missing json")

        for key in kwargs:
            setattr(self, key, kwargs[key])

    def toJson(self) -> Json:
        return {"id": self.id, "type": self.type.value, "path": self.path}

    def __str__(self):
        return f"Manifest(id={self.id}, type={self.type}, path={self.path})"

    def __repr__(self):
        return f"Manifest({id})"

    def dirname(self) -> str:
        return os.path.dirname(self.path)


class Extern:
    git: str = ""
    tag: str = ""

    def __init__(self, json: Json = None, strict: bool = True, **kwargs: Any):
        if json is not None:
            if "git" not in json and strict:
                raise RuntimeError("Missing git")

            self.git = json["git"]

            if "tag" not in json and strict:
                raise RuntimeError("Missing tag")

            self.tag = json["tag"]
        elif strict:
            raise RuntimeError("Missing json")

        for key in kwargs:
            setattr(self, key, kwargs[key])

    def toJson(self) -> Json:
        return {"git": self.git, "tag": self.tag}

    def __str__(self):
        return f"Extern(git={self.git}, tag={self.tag})"

    def __repr__(self):
        return f"Extern({self.git})"


class Project(Manifest):
    description: str = ""
    extern: dict[str, Extern] = {}

    def __init__(
        self, json: Json = None, path: str = "", strict: bool = True, **kwargs: Any
    ):
        if json is not None:
            if "description" not in json and strict:
                raise RuntimeError("Missing description")

            self.description = json["description"]

            self.extern = {k: Extern(v) for k, v in json.get("extern", {}).items()}
        elif strict:
            raise RuntimeError("Missing json")

        super().__init__(json, path, strict, **kwargs)

    def toJson(self) -> Json:
        return {
            **super().toJson(),
            "description": self.description,
            "extern": {k: v.toJson() for k, v in self.extern.items()},
        }

    def __str__(self):
        return f"ProjectManifest(id={self.id}, type={self.type}, path={self.path}, description={self.description}, extern={self.extern})"

    def __repr__(self):
        return f"ProjectManifest({self.id})"


class Tool:
    cmd: str = ""
    args: list[str] = []
    files: list[str] = []

    def __init__(self, json: Json = None, strict: bool = True, **kwargs: Any):
        if json is not None:
            if "cmd" not in json and strict:
                raise RuntimeError("Missing cmd")

            self.cmd = json.get("cmd", self.cmd)

            if "args" not in json and strict:
                raise RuntimeError("Missing args")

            self.args = json.get("args", [])

            self.files = json.get("files", [])
        elif strict:
            raise RuntimeError("Missing json")

        for key in kwargs:
            setattr(self, key, kwargs[key])

    def toJson(self) -> Json:
        return {"cmd": self.cmd, "args": self.args, "files": self.files}

    def __str__(self):
        return f"Tool(cmd={self.cmd}, args={self.args}, files={self.files})"

    def __repr__(self):
        return f"Tool({self.cmd})"


Tools = dict[str, Tool]


class Target(Manifest):
    props: Props
    tools: Tools
    routing: dict[str, str]

    def __init__(
        self, json: Json = None, path: str = "", strict: bool = True, **kwargs: Any
    ):
        if json is not None:
            if "props" not in json and strict:
                raise RuntimeError("Missing props")

            self.props = json["props"]

            if "tools" not in json and strict:
                raise RuntimeError("Missing tools")

            self.tools = {k: Tool(v) for k, v in json["tools"].items()}

            self.routing = json.get("routing", {})

        super().__init__(json, path, strict, **kwargs)

    def toJson(self) -> Json:
        return {
            **super().toJson(),
            "props": self.props,
            "tools": {k: v.toJson() for k, v in self.tools.items()},
            "routing": self.routing,
        }

    def __repr__(self):
        return f"TargetManifest({self.id})"

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


class Component(Manifest):
    decription: str = "(No description)"
    props: Props = {}
    tools: Tools = {}
    enableIf: dict[str, list[Any]] = {}
    requires: list[str] = []
    provides: list[str] = []
    subdirs: list[str] = []

    def __init__(
        self, json: Json = None, path: str = "", strict: bool = True, **kwargs: Any
    ):
        if json is not None:
            self.decription = json.get("description", self.decription)
            self.props = json.get("props", self.props)
            self.tools = {
                k: Tool(v, strict=False) for k, v in json.get("tools", {}).items()
            }
            self.enableIf = json.get("enableIf", self.enableIf)
            self.requires = json.get("requires", self.requires)
            self.provides = json.get("provides", self.provides)
            self.subdirs = list(
                map(
                    lambda x: os.path.join(os.path.dirname(path), x),
                    json.get("subdirs", [""]),
                )
            )

        super().__init__(json, path, strict, **kwargs)

    def toJson(self) -> Json:
        return {
            **super().toJson(),
            "description": self.decription,
            "props": self.props,
            "tools": {k: v.toJson() for k, v in self.tools.items()},
            "enableIf": self.enableIf,
            "requires": self.requires,
            "provides": self.provides,
            "subdirs": self.subdirs,
        }

    def __repr__(self):
        return f"ComponentManifest({self.id})"

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
