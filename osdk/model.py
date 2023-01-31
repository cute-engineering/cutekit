import os
from enum import Enum
from typing import Any
from json import JSONEncoder

from osdk.jexpr import Json, evalRead
from osdk.logger import Logger
from osdk import shell, const, utils


logger = Logger("model")

Props = dict[str, Any]


class Type(Enum):
    TARGET = "target"
    LIB = "lib"
    EXE = "exe"


class Manifest:
    id: str
    type: Type
    path: str = ""

    def __init__(self,  json: Json, path: str):
        if not "id" in json:
            raise ValueError("Missing id")

        self.id = json["id"]

        if not "type" in json:
            raise ValueError("Missing type")

        self.type = Type(json["type"])

        self.path = path

    def __str__(self):
        return f"Manifest(id={self.id}, type={self.type}, path={self.path})"

    def __repr__(self):
        return f"Manifest({id})"

    def dirname(self) -> str:
        return os.path.dirname(self.path)


class Tool:
    cmd: str
    args: list[str]
    files: list[str] = []

    def __init__(self, json: Json):
        if not "cmd" in json:
            raise ValueError("Missing cmd")
        self.cmd = json["cmd"]

        if not "args" in json:
            raise ValueError("Missing args")
        self.args = json["args"]

        self.files = json.get("files", [])

    def __str__(self):
        return f"Tool(cmd={self.cmd}, args={self.args})"


class TargetManifest(Manifest):
    props: Props
    tools: dict[str, Tool]
    routing: dict[str, str]

    def __init__(self, json: Json, path: str):
        super().__init__(json, path)

        if not "props" in json:
            raise ValueError("Missing props")

        self.props = json["props"]

        if not "tools" in json:
            raise ValueError("Missing tools")

        self.tools = {k: Tool(v) for k, v in json["tools"].items()}

        self.routing = json.get("routing", {})

    def __str__(self):
        return f"TargetManifest(" + \
            "id={self.id}, " + \
            "type={self.type}, " + \
            "props={self.props}, " + \
            "tools={self.tools}, " + \
            "path={self.path}" + \
            ")"

    def __repr__(self):
        return f"TargetManifest({self.id})"

    def route(self, componentSpec: str):
        return self.routing[componentSpec] if componentSpec in self.routing else componentSpec

    def hashid(self) -> str:
        return utils.hash((self.props, self.tools), cls=ModelEncoder)

    def builddir(self) -> str:
        return f"{const.BUILD_DIR}/{self.id}-{self.hashid()[:8]}"


class ComponentManifest(Manifest):
    decription: str
    props: Props
    enableIf: dict[str, list[Any]]
    requires: list[str]
    provides: list[str]

    def __init__(self, json: Json, path: str):
        super().__init__(json, path)

        self.decription = json.get("description", "(No description)")
        self.props = json.get("props", {})
        self.enableIf = json.get("enableIf", {})
        self.requires = json.get("requires", [])
        self.provides = json.get("provides", [])

    def __str__(self):
        return f"ComponentManifest(" + \
            "id={self.id}, " + \
            "type={self.type}, " + \
            "description={self.decription}, " + \
            "requires={self.requires}, " + \
            "provides={self.provides}, " + \
            "injects={self.injects}, " + \
            "deps={self.deps}, " + \
            "path={self.path})"

    def __repr__(self):
        return f"ComponentManifest({self.id})"

    def isEnabled(self, target: TargetManifest):
        for k, v in self.enableIf.items():
            if not k in target.props:
                logger.log(
                    f"Component {self.id} disabled by missing {k} in target")
                return False

            if not target.props[k] in v:
                logger.log(
                    f"Component {self.id} disabled by {k}={target.props[k]} not in {v}")
                return False

        return True


class ModelEncoder(JSONEncoder):
    def default(self, o):
        if isinstance(o, Manifest):
            return {
                "id": o.id,
                "type": o.type.value,
                "path": o.path
            }

        if isinstance(o, Type):
            return o.value

        if isinstance(o, Tool):
            return {
                "cmd": o.cmd,
                "args": o.args,
                "files": o.files
            }

        if isinstance(o, TargetManifest):
            return {
                "id": o.id,
                "type": o.type.value,
                "props": o.props,
                "tools": o.tools,
                "routing": o.routing,
                "path": o.path
            }

        if isinstance(o, ComponentManifest):
            return {
                "id": o.id,
                "type": o.type.value,
                "description": o.decription,
                "props": o.props,
                "enableIf": o.enableIf,
                "requires": o.requires,
                "provides": o.provides,
                "path": o.path
            }

        return super().default(o)
