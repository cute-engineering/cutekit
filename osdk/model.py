import os
from enum import Enum
from typing import Any
from json import JSONEncoder

from osdk.jexpr import Json
from osdk.logger import Logger
from osdk import const, utils


logger = Logger("model")

Props = dict[str, Any]


class Type(Enum):
    UNKNOWN = "unknown"
    TARGET = "target"
    LIB = "lib"
    EXE = "exe"


class Manifest:
    id: str = ""
    type: Type = Type.UNKNOWN
    path: str = ""

    def __init__(self,  json: Json = None, path: str = "", strict=True, **kwargs):
        if json is not None:
            if not "id" in json:
                raise ValueError("Missing id")

            self.id = json["id"]

            if not "type" in json and strict:
                raise ValueError("Missing type")

            self.type = Type(json["type"])

            self.path = path
        elif strict:
            raise ValueError("Missing json")

        for key in kwargs:
            setattr(self, key, kwargs[key])

    def __str__(self):
        return f"Manifest(id={self.id}, type={self.type}, path={self.path})"

    def __repr__(self):
        return f"Manifest({id})"

    def dirname(self) -> str:
        return os.path.dirname(self.path)


class Tool:
    cmd: str = ""
    args: list[str] = []
    files: list[str] = []

    def __init__(self, json: Json = None, strict=True, **kwargs):
        if json is not None:
            if not "cmd" in json and strict:
                raise ValueError("Missing cmd")

            self.cmd = json.get("cmd", self.cmd)

            if not "args" in json and strict:
                raise ValueError("Missing args")

            self.args = json.get("args", [])

            self.files = json.get("files", [])
        elif strict:
            raise ValueError("Missing json")

        for key in kwargs:
            setattr(self, key, kwargs[key])

    def __str__(self):
        return f"Tool(cmd={self.cmd}, args={self.args}, files={self.files})"

    def __repr__(self):
        return f"Tool({self.cmd})"


Tools = dict[str, Tool]


class TargetManifest(Manifest):
    props: Props
    tools: Tools
    routing: dict[str, str]

    def __init__(self, json: Json = None, path: str = "", strict=True, **kwargs):
        if json is not None:
            if not "props" in json and strict:
                raise ValueError("Missing props")

            self.props = json["props"]

            if not "tools" in json and strict:
                raise ValueError("Missing tools")

            self.tools = {k: Tool(v) for k, v in json["tools"].items()}

            self.routing = json.get("routing", {})

        super().__init__(json, path, strict, **kwargs)

    def __repr__(self):
        return f"TargetManifest({self.id})"

    def route(self, componentSpec: str):
        return self.routing[componentSpec] if componentSpec in self.routing else componentSpec

    def cdefs(self) -> list[str]:
        defines: list[str] = []

        for key in self.props:
            macroname = key.lower().replace("-", "_")
            prop = self.props[key]
            macrovalue = str(prop).lower().replace(" ", "_").replace("-", "_")
            if isinstance(prop, bool):
                if prop:
                    defines += [f"-D__osdk_{macroname}__"]
            else:
                defines += [f"-D__osdk_{macroname}_{macrovalue}__"]

        return defines


class ComponentManifest(Manifest):
    decription: str = "(No description)"
    props: Props = {}
    tools: Tools = {}
    enableIf: dict[str, list[Any]] = {}
    requires: list[str] = []
    provides: list[str] = []

    def __init__(self, json: Json = None, path: str = "", strict=True, **kwargs):
        if json is not None:
            self.decription = json.get("description", self.decription)
            self.props = json.get("props", self.props)
            self.tools = {k: Tool(v, strict=False)
                          for k, v in json.get("tools", {}).items()}
            self.enableIf = json.get("enableIf", self.enableIf)
            self.requires = json.get("requires", self.requires)
            self.provides = json.get("provides", self.provides)

        super().__init__(json, path, strict, **kwargs)

    def __repr__(self):
        return f"ComponentManifest({self.id})"

    def isEnabled(self, target: TargetManifest) -> tuple[bool, str]:
        for k, v in self.enableIf.items():
            if not k in target.props:
                logger.log(
                    f"Component {self.id} disabled by missing {k} in target")
                return False, f"Missing props '{k}' in target"

            if not target.props[k] in v:
                vStrs = [f"'{str(x)}'" for x in v]
                logger.log(
                    f"Component {self.id} disabled by {k}={target.props[k]} not in {v}")
                return False, f"Props missmatch for '{k}': Got '{target.props[k]}' but expected {', '.join(vStrs)}"

        return True, ""
