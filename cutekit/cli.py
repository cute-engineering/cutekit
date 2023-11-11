import inspect

from typing import Optional, Union, Callable
from dataclasses import dataclass


Value = Union[str, bool, int]


class Args:
    opts: dict[str, Value]
    args: list[str]

    def __init__(self):
        self.opts = {}
        self.args = []

    def consumePrefix(self, prefix: str) -> dict[str, Value]:
        result: dict[str, Value] = {}
        copy = self.opts.copy()
        for key, value in copy.items():
            if key.startswith(prefix):
                result[key[len(prefix) :]] = value
                del self.opts[key]
        return result

    def consumeOpt(self, key: str, default: Value = False) -> Value:
        if key in self.opts:
            result = self.opts[key]
            del self.opts[key]
            return result
        return default

    def tryConsumeOpt(self, key: str) -> Optional[Value]:
        if key in self.opts:
            result = self.opts[key]
            del self.opts[key]
            return result
        return None

    def consumeArg(self, default: Optional[str] = None) -> Optional[str]:
        if len(self.args) == 0:
            return default

        first = self.args[0]
        del self.args[0]
        return first


def parse(args: list[str]) -> Args:
    result = Args()

    for arg in args:
        if arg.startswith("--"):
            if "=" in arg:
                key, value = arg[2:].split("=", 1)
                result.opts[key] = value
            else:
                result.opts[arg[2:]] = True
        else:
            result.args.append(arg)

    return result


Callback = Callable[[Args], None]


@dataclass
class Command:
    shortName: str
    longName: str
    helpText: str
    isPlugin: bool
    callback: Callback


commands: list[Command] = []


def append(command: Command):
    command.isPlugin = True
    commands.append(command)
    commands.sort(key=lambda c: c.shortName or c.longName)


def command(shortName: str, longName: str, helpText: str):
    curframe = inspect.currentframe()
    calframe = inspect.getouterframes(curframe, 2)

    def wrap(fn: Callable[[Args], None]):
        commands.append(
            Command(shortName, longName, helpText, calframe[1].filename != __file__, fn)
        )
        return fn

    return wrap
