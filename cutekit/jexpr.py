import os
import re
import json
import datetime

from pathlib import Path
from typing import Any, Callable, Optional
from . import cli


Jexpr = dict[str, "Jexpr"] | list["Jexpr"] | str | bool | float | int | None
_globals: dict[str, Any] = dict()


def _isListExpr(expr: Jexpr) -> bool:
    return (
        isinstance(expr, list)
        and len(expr) > 0
        and isinstance(expr[0], str)
        and expr[0].startswith("@")
    )


def _extractStr(expr: str, expand: Callable[[Jexpr], Jexpr]) -> str:
    res = ""
    depth = 0
    strStart = 0
    exprStart = 0
    for i, c in enumerate(expr):
        if c == "{":
            if depth == 0:
                res += expr[strStart:i]
                exprStart = i + 1
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                subexpr = expr[exprStart:i]
                try:
                    res += str(expand(subexpr))
                except Exception as e:
                    raise ValueError(f"Failed to expand '{subexpr}': {e}")

                strStart = i + 1

    if depth != 0:
        raise ValueError(f"Unbalanced braces in {expr}")
    res += expr[strStart:]
    return res


def expand(
    expr: Jexpr,
    locals: dict[str, Any] | None = None,
    globals: dict[str, Any] = _globals,
    depth: int = 0,
) -> Jexpr:
    """
    Expand a Jexpr expression.
    """

    def _expand(expr: Jexpr) -> Jexpr:
        return expand(expr, locals=locals, globals=globals, depth=depth + 1)

    if depth > 10:
        raise ValueError(f"Recursion limit reached: {expr}")

    if isinstance(expr, dict):
        result: dict[str, Jexpr] = {}
        for k in expr:
            key = _expand(k)
            result[str(key)] = _expand(expr[k])
        return result

    elif _isListExpr(expr):
        if not isinstance(expr, list):
            raise ValueError(f"Expected list, got {expr}")

        if not isinstance(expr[0], str):
            raise ValueError(f"Expected string, got {expr[0]}")

        fName = _expand(expr[0][1:])
        fVal = eval(str(fName), globals, locals)
        res = fVal(*_expand(expr[1:]))
        return _expand(res)

    elif isinstance(expr, list):
        return [_expand(e) for e in expr]

    elif isinstance(expr, str):
        return _extractStr(
            expr,
            lambda e: eval(str(e), globals, locals)
            if not (isinstance(e, str) and e.startswith("{") and e.endswith("}"))
            else e,
        )

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


def read(path: Path) -> Jexpr:
    """
    Read a JSON or TOML file.
    """
    try:
        with open(path, "r", encoding="utf8") as f:
            if path.suffix == ".toml":
                return _loadToml(f.read())
            else:
                return json.loads(f.read())
    except Exception as e:
        raise RuntimeError(f"Failed to read {path}: {e}")


def include(
    path: Path, locals: dict[str, Any] | None = None, globals: dict[str, Any] = _globals
) -> Jexpr:
    """
    Read and expand a JSON or TOML file.
    """
    globalsWithFile = globals.copy()
    globalsWithFile["__file__"] = path
    return expand(read(path), locals, globals)


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
    obj = _globals
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


expose("jexpr.include", lambda path: include(Path(path)))
expose("jexpr.expand", lambda expr: expand(expr))
expose("jexpr.read", lambda path: read(Path(path)))

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
    print(json.dumps(include(Path(args.path)), indent=2))
    endTime = datetime.datetime.now()

    delaMs = (endTime - startTime).total_seconds() * 1000

    print(f"\nElapsed time: {delaMs:.2f}ms")
