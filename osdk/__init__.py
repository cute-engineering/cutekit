import importlib
import shutil
import sys
import random
from types import ModuleType

import osdk.build as build
import osdk.utils as utils
import osdk.targets as targets


CMDS = {}


def parseOptions(args: list[str]) -> dict:
    result = {
        'opts': {},
        'args': []
    }

    for arg in args:
        if arg.startswith("--"):
            if "=" in arg:
                key, value = arg[2:].split("=", 1)
                result['opts'][key] = value
            else:
                result['opts'][arg[2:]] = True
        else:
            result['args'].append(arg)

    return result


def runCmd(opts: dict, args: list[str]) -> None:
    if len(args) == 0:
        print(f"Usage: {args[0]} run <component>")
        sys.exit(1)

    out = build.buildOne(opts.get('target', 'host-clang'), args[0])

    print(f"{utils.Colors.BOLD}Running: {args[0]}{utils.Colors.RESET}")
    utils.runCmd(out, *args[1:])


def buildCmd(opts: dict, args: list[str]) -> None:
    targetName = opts.get('target', 'host-clang')

    if len(args) == 0:
        build.buildAll(targetName)
    else:
        for component in args:
            build.buildOne(targetName, component)


def cleanCmd(opts: dict, args: list[str]) -> None:
    shutil.rmtree(".build", ignore_errors=True)


def nukeCmd(opts: dict, args: list[str]) -> None:
    shutil.rmtree(".build", ignore_errors=True)
    shutil.rmtree(".cache", ignore_errors=True)


def idCmd(opts: dict, args: list[str]) -> None:
    i = hex(random.randint(0, 2**64))
    print("64bit: " + i)
    print("32bit: " + i[:10])


def helpCmd(opts: dict, args: list[str]) -> None:
    print(f"Usage: osdk <command> [options...] [<args...>]")
    print("")

    print("Description:")
    print("   Operating System Development Kit.")
    print("")

    print("Commands:")
    for cmd in CMDS:
        print("  " + cmd + " - " + CMDS[cmd]["desc"])
    print("")

    print("Targets:")
    availableTargets = targets.available()
    if len(availableTargets) == 0:
        print("   No targets available")
    else:
        for targetName in targets.available():
            print("  " + targetName)
    print("")

    print("Variants:")
    for var in targets.VARIANTS:
        print("  " + var)
    print("")


CMDS = {
    "run": {
        "func": runCmd,
        "desc": "Run a component on the host",
    },
    "build": {
        "func": buildCmd,
        "desc": "Build one or more components",
    },
    "clean": {
        "func": cleanCmd,
        "desc": "Clean the build directory",
    },
    "nuke": {
        "func": nukeCmd,
        "desc": "Clean the build directory and cache",
    },
    "help": {
        "func": helpCmd,
        "desc": "Show this help message",
    },
}


def loadPlugin(path: str) -> ModuleType:
    """Load a plugin from a path"""
    spec = importlib.util.spec_from_file_location("plugin", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


for files in utils.tryListDir("meta/plugins"):
    if files.endswith(".py"):
        plugin = loadPlugin(f"meta/plugins/{files}")
        CMDS[plugin.__plugin__["name"]] = plugin.__plugin__


def main():
    argv = sys.argv
    try:
        if len(argv) < 2:
            helpCmd({}, [])
        else:
            o = parseOptions(argv[2:])
            if not argv[1] in CMDS:
                print(f"Unknown command: {argv[1]}")
                print("")
                print(f"Use '{argv[0]} help' for a list of commands")
                return 1
            CMDS[argv[1]]["func"](o['opts'], o['args'])
            return 0
    except utils.CliException as e:
        print()
        print(f"{utils.Colors.RED}{e.msg}{utils.Colors.RESET}")
        return 1
