import enum
import inspect
import logging
import sys
import dataclasses as dt

from functools import partial
from pathlib import Path
from typing import Any, NewType, Optional, Union, Callable, Generic, get_origin, get_args

from . import const, vt100, utils

Value = Union[str, bool, int]

_logger = logging.getLogger(__name__)


# --- Arg parsing -------------------------------------------------------------


@dt.dataclass
class Arg(Generic[utils.T]):
    shortName: str
    longName: str
    description: str
    default: Optional[utils.T] = None

    def __get__(self, instance, owner):
        if instance is None:
            return self

        return instance.__dict__.get(self.longName, self.default)


@dt.dataclass
class FreeFormArg(Generic[utils.T]):
    description: str
    default: Optional[utils.T] = None

    def __get__(self, instance, owner):
        if instance is None:
            return self

        return self.default

class ParserState(enum.Enum):
    FreeForm = enum.auto()
    ShortArg = enum.auto()

RawArg = NewType("RawArg", str)

class CutekitArgs:
    cmd: FreeFormArg[str] = FreeFormArg("Command to execute")
    verbose: Arg[bool] = Arg("v", "verbose", "Enable verbose logging")
    safemode: Arg[bool] = Arg("s", "safe", "Enable safe mode")
    pod: Arg[bool] = Arg("p", "enable-pod", "Enable pod", default=False)
    podName: Arg[str] = Arg("n", "pod-name", "The name of the pod", default="")


def parse(argv: list[str], argType: type) -> Any:
    def set_value(options: dict[str, Any], name: str, value: Any):
        if name is not options:
            options[name] = value
        else:
            raise RuntimeError(f"{name} is already set")

    def is_optional(t: type) -> bool:
        return get_origin(t) is Union and type(None) in get_args(t)

    def freeforms_get(argType: type) -> tuple[list[str], list[str]]:
        freeforms = []
        required_freeforms = []

        found_optional = False
        for arg, anno in [
            arg
            for arg in argType.__annotations__.items()
            if get_origin(arg[1]) is FreeFormArg
        ]:
            freeforms.append(arg)
            if is_optional(get_args(anno)[0]):
                found_optional = True
            elif found_optional:
                raise RuntimeError(
                    f"Required arguments must come before optional arguments"
                )
            else:
                required_freeforms.append(arg)

        return (freeforms, required_freeforms)

    result = argType()
    options: dict[str, Any] = {}
    args: dict[str, partial] = {}
    freeforms: list[Any] = []

    state = ParserState.FreeForm
    current_arg: Optional[str] = None

    for arg in dir(argType):
        if isinstance(getattr(argType, arg), Arg):
            args[getattr(argType, arg).shortName] = partial(set_value, options, arg)
            args[getattr(argType, arg).longName] = partial(set_value, options, arg)

    i = 0
    while i < len(argv):
        match state:
            case ParserState.FreeForm:
                if argv[i] == "--":
                    freeargs = argv[i + 1:]
                    i += 1
                    break
                if argv[i].startswith("--"):
                    if "=" in argv[i]:
                        # --name=value
                        name, value = argv[i][2:].split("=", 1)
                        if name in args:
                            args[name](value)
                    else:
                        # --name -> the value will be True
                        if argv[i][2:] in args:
                            args[argv[i][2:]](True)
                elif argv[i].startswith("-"):
                    if len(argv[i][1:]) > 1:
                        for c in argv[i][1:]:
                            # -abc -> a, b, c are all True
                            if c in args:
                                args[c](True)
                    else:
                        state = ParserState.ShortArg
                        current_arg = argv[i][1:]
                else:
                    freeforms.append(argv[i])

                i += 1
            case ParserState.ShortArg:
                if argv[i].startswith("-"):
                    # -a -b 4 -> a is True
                    if current_arg in args:
                        args[current_arg](True)
                else:
                    # -a 4 -> a is 4
                    if current_arg in args:
                        args[current_arg](argv[i])

                i += 1
                current_arg = None
                state = ParserState.FreeForm

    freeforms_all, required_freeforms = freeforms_get(argType)
    if len(freeforms) < len(required_freeforms):
        raise RuntimeError(
            f"Missing arguments: {', '.join(required_freeforms[len(freeforms):])}"
        )
    if len(freeforms) > len(freeforms_all):
        raise RuntimeError(f"Too many arguments")

    for i, freeform in enumerate(freeforms):
        setattr(result, freeforms_all[i], freeform)

    # missing arguments
    missing = set(
        [
            arg[0]
            for arg in argType.__annotations__
            if get_origin(arg[1]) is Arg and getattr(argType, arg[0]).default is None
        ]
    ) - set(options.keys())
    if missing:
        raise RuntimeError(f"Missing arguments: {', '.join(missing)}")

    for key, value in options.items():
        field_type = get_args(argType.__annotations__[key])[0]
        setattr(result, key, field_type(value))

    raw_args = [arg[0] for arg in argType.__annotations__.items() if arg[1] is RawArg]
    
    if len(raw_args) > 1:
        raise RuntimeError(f"Only one RawArg is allowed")
    elif len(raw_args) == 1:
        setattr(result, raw_args[0], freeargs)

    return result


Callback = Callable[[Any], None] | Callable[[], None]


@dt.dataclass
class Command:
    shortName: Optional[str]
    longName: str
    helpText: str
    isPlugin: bool
    callback: Callback
    argType: Optional[type]

    subcommands: dict[str, "Command"] = dt.field(default_factory=dict)


commands: dict[str, Command] = {}


def command(shortName: Optional[str], longName: str, helpText: str):
    curframe = inspect.currentframe()
    calframe = inspect.getouterframes(curframe, 2)

    def wrap(fn: Callback):
        _logger.debug(f"Registering command {longName}")
        if len(fn.__annotations__) == 0:
            argType = None
        else:
            argType = list(fn.__annotations__.values())[0]

        path = longName.split("/")
        parent = commands
        for p in path[:-1]:
            parent = parent[p].subcommands
        parent[path[-1]] = Command(
            shortName,
            path[-1],
            helpText,
            Path(calframe[1].filename).parent != Path(__file__).parent,
            fn,
            argType
        )

        return fn

    return wrap


# --- Builtins Commands ------------------------------------------------------ #


@command("u", "usage", "Show usage information")
def usage():
    print(f"Usage: {const.ARGV0} <command> [args...]")


def error(msg: str) -> None:
    print(f"{vt100.RED}Error:{vt100.RESET} {msg}\n", file=sys.stderr)


def warning(msg: str) -> None:
    print(f"{vt100.YELLOW}Warning:{vt100.RESET} {msg}\n", file=sys.stderr)


def ask(msg: str, default: Optional[bool] = None) -> bool:
    if default is None:
        msg = f"{msg} [y/n] "
    elif default:
        msg = f"{msg} [Y/n] "
    else:
        msg = f"{msg} [y/N] "

    while True:
        result = input(msg).lower()
        if result in ("y", "yes"):
            return True
        elif result in ("n", "no"):
            return False
        elif result == "" and default is not None:
            return default


@command("h", "help", "Show this help message")
def helpCmd():
    usage()

    print()

    vt100.title("Description")
    print(f"    {const.DESCRIPTION}")

    print()
    vt100.title("Commands")
    for cmd in sorted(commands.values(), key=lambda c: c.longName):
        if cmd.longName.startswith("_") or len(cmd.subcommands) > 0:
            continue

        pluginText = ""
        if cmd.isPlugin:
            pluginText = f"{vt100.CYAN}(plugin){vt100.RESET}"

        print(
            f" {vt100.GREEN}{cmd.shortName or ' '}{vt100.RESET}  {cmd.longName} - {cmd.helpText} {pluginText}"
        )

    for cmd in sorted(commands.values(), key=lambda c: c.longName):
        if cmd.longName.startswith("_") or len(cmd.subcommands) == 0:
            continue

        print()
        vt100.title(f"{cmd.longName.capitalize()} - {cmd.helpText}")
        for subcmd in sorted(cmd.subcommands.values(), key=lambda c: c.longName):
            pluginText = ""
            if subcmd.isPlugin:
                pluginText = f"{vt100.CYAN}(plugin){vt100.RESET}"

            print(
                f"     {vt100.GREEN}{subcmd.shortName or ' '}{vt100.RESET}  {subcmd.longName} - {subcmd.helpText} {pluginText}"
            )

    print()
    vt100.title("Logging")
    print("    Logs are stored in:")
    print(f"     - {const.PROJECT_LOG_FILE}")
    print(f"     - {const.GLOBAL_LOG_FILE}")


@command("v", "version", "Show current version")
def versionCmd():
    print(f"CuteKit v{const.VERSION_STR}")


def exec(cmd: str, args: list[str], cmds: dict[str, Command]=commands):
    for c in cmds.values():
        if c.shortName == cmd or c.longName == cmd:
            if len(c.subcommands) > 0:
                exec(args[0], args[1:], c.subcommands)
                return
            else:
                if c.argType is not None:
                    c.callback(parse(args[1:], c.argType)) # type: ignore
                else:
                    c.callback() # type: ignore 
                return

    raise RuntimeError(f"Unknown command {cmd}")
