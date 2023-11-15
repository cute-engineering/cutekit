import inspect
import logging
import sys

from pathlib import Path
from typing import Optional, Union, Callable
from dataclasses import dataclass

from . import const, vt100

Value = Union[str, bool, int]

_logger = logging.getLogger(__name__)


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
    shortName: Optional[str]
    longName: str
    helpText: str
    isPlugin: bool
    callback: Callback


commands: list[Command] = []


def command(shortName: Optional[str], longName: str, helpText: str):
    curframe = inspect.currentframe()
    calframe = inspect.getouterframes(curframe, 2)

    def wrap(fn: Callable[[Args], None]):
        _logger.debug(f"Registering command {longName}")
        commands.append(
            Command(
                shortName,
                longName,
                helpText,
                Path(calframe[1].filename).parent != Path(__file__).parent,
                fn,
            )
        )
        return fn

    return wrap


# --- Builtins Commands ------------------------------------------------------ #


@command("u", "usage", "Show usage information")
def usage(args: Optional[Args] = None):
    print(f"Usage: {const.ARGV0} <command> [args...]")


def error(msg: str) -> None:
    print(f"{vt100.RED}Error:{vt100.RESET} {msg}\n", file=sys.stderr)


@command("h", "help", "Show this help message")
def helpCmd(args: Args):
    usage()

    print()

    vt100.title("Description")
    print(f"    {const.DESCRIPTION}")

    print()
    vt100.title("Commands")
    for cmd in sorted(commands, key=lambda c: c.longName):
        if cmd.longName.startswith("_"):
            continue

        pluginText = ""
        if cmd.isPlugin:
            pluginText = f"{vt100.CYAN}(plugin){vt100.RESET}"

        print(
            f" {vt100.GREEN}{cmd.shortName or ' '}{vt100.RESET}  {cmd.longName} - {cmd.helpText} {pluginText}"
        )

    print()
    vt100.title("Logging")
    print("    Logs are stored in:")
    print(f"     - {const.PROJECT_LOG_FILE}")
    print(f"     - {const.GLOBAL_LOG_FILE}")


@command("v", "version", "Show current version")
def versionCmd(args: Args):
    print(f"CuteKit v{const.VERSION_STR}")


def exec(args: Args):
    cmd = args.consumeArg()

    if cmd is None:
        raise RuntimeError("No command specified")

    for c in commands:
        if c.shortName == cmd or c.longName == cmd:
            c.callback(args)
            return

    raise RuntimeError(f"Unknown command {cmd}")
