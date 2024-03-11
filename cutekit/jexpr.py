import os
import re
import inspect
import json

import datetime
import asyncio as aio
import aiofiles as aiof

from pathlib import Path
from typing import Any, Optional

from . import cli


REXPR = re.compile("{[^}]*}")

Jexpr = dict[str, "Jexpr"] | list["Jexpr"] | str | bool | float | int | None
GLOBALS: dict[str, Any] = dict()


def _isListExpr(expr: Jexpr) -> bool:
    return (
        isinstance(expr, list)
        and len(expr) > 0
        and isinstance(expr[0], str)
        and expr[0].startswith("@")
    )


async def _evalListExprAsync(
    expr: list[Jexpr],
    locals: dict[str, Any] | None,
    globals: dict[str, Any],
    depth: int = 0,
) -> Jexpr:
    def _ctx(f):
        return lambda *args, **kwargs: f(
            *args, **kwargs, locals=locals, globals=globals, depth=depth + 1
        )

    if not isinstance(expr, list):
        raise ValueError(f"Expected list, got {expr}")

    if not isinstance(expr[0], str):
        raise ValueError(f"Expected string, got {expr[0]}")

    fName = await _ctx(expandAsync)(expr[0][1:])
    fVal = eval(fName, globals, locals)
    return fVal(*await _ctx(expandAsync)(expr[1:]))


async def _evalStrExprAsync(
    expr: str, locals: dict[str, Any] | None, globals: dict[str, Any], depth: int
) -> str:
    def _ctx(f):
        return lambda *args, **kwargs: f(
            *args, **kwargs, locals=locals, globals=globals, depth=depth
        )

    result = ""
    while span := REXPR.search(expr):
        result += expr[: span.start()]
        code = span.group()[1:-1]
        value = eval(code, globals, locals)
        result += str(await _ctx(expandAsync)(value))
        expr = expr[span.end() :]
    result += expr
    return result


async def expandAsync(
    expr: Jexpr,
    locals: dict[str, Any] | None = None,
    globals: dict[str, Any] = GLOBALS,
    depth: int = 0,
) -> Jexpr:
    """
    Expand a Jexpr expression.
    """

    def _ctx(f):
        return lambda *args, **kwargs: f(
            *args, **kwargs, locals=locals, globals=globals, depth=depth + 1
        )

    if depth > 10:
        raise ValueError(f"Recursion limit reached: {expr}")

    if inspect.isawaitable(expr):
        expr = await expr

    if isinstance(expr, dict):
        result: dict[str, Jexpr] = {}
        for k in expr:
            key = await _ctx(expandAsync)(k)
            result[key] = await _ctx(expandAsync)(expr[k])
        return result

    elif _isListExpr(expr):
        return await _ctx(_evalListExprAsync)(expr)

    elif isinstance(expr, list):
        return [await _ctx(expandAsync)(e) for e in expr]

    elif isinstance(expr, str):
        return await _ctx(_evalStrExprAsync)(expr)

    else:
        return expr


def _extractSchema(toml: str) -> Optional[str]:
    schemaRegex = re.compile(r"#:schema\s+(.*)")
    schema = schemaRegex.search(toml)
    return schema.group(1) if schema else None


def _loadToml(buf: str) -> Jexpr:
    try:
        import tomllib

        toml = tomllib.loads(buf)
        schema = _extractSchema(buf)
        if schema:
            toml["$schema"] = schema
        return toml
    except ImportError:
        raise RuntimeError(
            "In order to read TOML files, you need to upgrade to Python3.11 or higher."
        )


async def readAsync(path: Path) -> Jexpr:
    """
    Read a JSON or TOML file.
    """
    try:
        async with aiof.open(path, "r") as f:
            if path.suffix == ".toml":
                return _loadToml(await f.read())
            else:
                return json.loads(await f.read())
    except Exception as e:
        raise RuntimeError(f"Failed to read {path}: {e}")


async def includeAsync(
    path: Path, locals: dict[str, Any] | None = None, globals: dict[str, Any] = GLOBALS
) -> Jexpr:
    """
    Read and expand a JSON or TOML file.
    """
    globalsWithFile = globals.copy()
    globalsWithFile["__file__"] = path
    return await expandAsync(await readAsync(path), locals, globals)


def include(
    path: Path, locals: dict[str, Any] | None = None, globals: dict[str, Any] = GLOBALS
) -> Jexpr:
    """
    Read and expand a JSON or TOML file.
    """
    return aio.run(includeAsync(path, locals, globals))


def _assign(obj: dict, key: str, value: Any) -> None:
    if isinstance(obj, dict):
        obj[key] = value
    else:
        setattr(obj, key, value)


def _get(obj: dict, key: str) -> Any:
    if isinstance(obj, dict):
        return obj[key]
    else:
        return getattr(obj, key)


class Namespace: ...


def expose(path: str, value: Any) -> None:
    """
    Expose a value to the Jexpr environment.
    """
    els = path.split(".")
    obj = GLOBALS
    for el in els[:-1]:
        if el not in obj:
            _assign(obj, el, Namespace())
        obj = _get(obj, el)

    _assign(obj, els[-1], value)


def exposed(path: str) -> Any:
    """
    Decorator to expose a value to the Jexpr environment.
    """

    def decorator(value: Any) -> Any:
        expose(path, value)
        return value

    return decorator


def _union(lhs, rhs):
    if isinstance(lhs, dict):
        return {**lhs, **rhs}
    else:
        return lhs + rhs


def _relpath(*args):
    return os.path.normpath(os.path.join(os.path.dirname(__file__), *args))


expose("jexpr.include", lambda path: includeAsync(Path(path)))
expose("jexpr.expand", lambda expr: expandAsync(expr))
expose("jexpr.read", lambda path: readAsync(Path(path)))

expose("utils.relpath", _relpath)
expose("utils.union", _union)
expose("utils.concat", lambda *args: "".join(args))
expose("utils.first", lambda arg: arg[0] if arg else None)
expose("utils.last", lambda arg: arg[-1] if arg else None)


class EvalArgs:
    path: str = cli.operand("path", "Path to the file to evaluate.")


@cli.command(None, "jexpr", "Utilities for working with Jexpr files.")
def _():
    pass


@cli.command(None, "jexpr/eval", "Evaluate a Jexpr file.")
def _(args: EvalArgs):
    startTime = datetime.datetime.now()
    print(json.dumps(aio.run(includeAsync(Path(args.path))), indent=2))
    endTime = datetime.datetime.now()

    delaMs = (endTime - startTime).total_seconds() * 1000

    print(f"\nElapsed time: {delaMs:.2f}ms")
