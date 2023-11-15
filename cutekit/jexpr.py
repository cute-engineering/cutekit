import os
import json
import re
import tomllib

from pathlib import Path

from typing import Any, Optional, cast, Callable, Final
from . import shell

Json = Any
Builtin = Callable[..., Json]

BUILTINS: Final[dict[str, Builtin]] = {
    "uname": lambda arg, ctx: getattr(shell.uname(), arg).lower(),
    "include": lambda arg, ctx: evalRead(Path(arg)),
    "evalRead": lambda arg, ctx: evalRead(Path(arg)),
    "join": lambda lhs, rhs, ctx: cast(
        Json, {**lhs, **rhs} if isinstance(lhs, dict) else lhs + rhs
    ),
    "concat": lambda *args, ctx: "".join(args),
    "first": lambda arg, ctx: arg[0],
    "last": lambda arg, ctx: arg[-1],
    "eval": lambda arg, ctx: eval(arg, ctx["filepath"]),
    "read": lambda arg, ctx: read(arg),
    "exec": lambda *args, ctx: shell.popen(*args).splitlines(),
    "latest": lambda arg, ctx: shell.latest(arg),
    "abspath": lambda *args, ctx: os.path.normpath(
        os.path.join(os.path.dirname(ctx["filepath"]), *args)
    ),
}


def eval(jexpr: Json, filePath: Path) -> Json:
    if isinstance(jexpr, dict):
        result = {}
        for k in cast(dict[str, Json], jexpr):
            result[k] = eval(jexpr[k], filePath)
        return cast(Json, result)
    elif isinstance(jexpr, list):
        jexpr = cast(list[Json], jexpr)
        if len(jexpr) > 0 and isinstance(jexpr[0], str) and jexpr[0].startswith("@"):
            funcName = jexpr[0][1:]
            if funcName in BUILTINS:
                return BUILTINS[funcName](
                    *eval(jexpr[1:], filePath), ctx={"filepath": filePath}
                )

            raise RuntimeError(f"Unknown macro {funcName}")
        else:
            return list(map(lambda j: eval(j, filePath), jexpr))
    else:
        return jexpr


def extraSchema(toml: str) -> Optional[str]:
    schemaRegex = re.compile(r"#:schema\s+(.*)")
    schema = schemaRegex.search(toml)
    return schema.group(1) if schema else None


def read(path: Path) -> Json:
    try:
        with open(path, "r") as f:
            if path.suffix == ".toml":
                tomlStr = f.read()
                toml = tomllib.loads(tomlStr)
                schema = extraSchema(tomlStr)
                if schema:
                    toml["$schema"] = schema
                return toml
            else:
                return json.load(f)
    except Exception as e:
        raise RuntimeError(f"Failed to read {path}: {e}")


def evalRead(path: Path) -> Json:
    data = read(path)
    return eval(data, path)
