from typing import Any, cast, Callable, Final
import json

import cutekit.shell as shell
from cutekit.compat import ensureSupportedManifest

Json = Any
Builtin = Callable[..., Json]

BUILTINS: Final[dict[str, Builtin]] = {
    "uname": lambda arg: getattr(shell.uname(), arg).lower(),
    "include": lambda arg: evalRead(arg),
    "evalRead": lambda arg: evalRead(arg),
    "join": lambda lhs, rhs: cast(Json, {**lhs, **rhs} if isinstance(lhs, dict) else lhs + rhs),
    "concat": lambda *args: "".join(args),
    "eval": lambda arg: eval(arg),
    "read": lambda arg: read(arg),
    "exec": lambda *args: shell.popen(*args).splitlines(),
    "latest": lambda arg: shell.latest(arg),
}


def eval(jexpr: Json) -> Json:
    if isinstance(jexpr, dict):
        result = {}
        for k in cast(dict[str, Json], jexpr):
            result[k] = eval(jexpr[k])
        return cast(Json, result)
    elif isinstance(jexpr, list):
        jexpr = cast(list[Json], jexpr)
        if len(jexpr) > 0 and isinstance(jexpr[0], str) and jexpr[0].startswith("@"):
            funcName = jexpr[0][1:]
            if funcName in BUILTINS:
                return BUILTINS[funcName](*eval(jexpr[1:]))

            raise RuntimeError(f"Unknown macro {funcName}")
        else:
            return list(map(eval, jexpr))
    else:
        return jexpr


def read(path: str) -> Json:
    try:
        with open(path, "r") as f:
            return json.load(f)
    except:
        raise RuntimeError(f"Failed to read {path}")


def evalRead(path: str) -> Json:
    data = read(path)
    ensureSupportedManifest(data, path)
    return eval(data)
