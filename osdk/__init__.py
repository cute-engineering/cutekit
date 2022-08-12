import importlib
import shutil
import sys
from types import ModuleType

import osdk.build as build
import osdk.utils as utils
import osdk.targets as targets
import osdk.manifests as manifests

__version__ = "0.2.1"

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


def propsFromOptions(opt: dict) -> dict:
    result = {}
    for key in opt:
        if key.startswith("prop:"):
            result[key[5:]] = opt[key]
    return result


def runCmd(opts: dict, args: list[str]) -> None:
    props = propsFromOptions(opts)

    if len(args) == 0:
        print(f"Usage: osdk run <component>")
        sys.exit(1)

    out = build.buildOne(opts.get('target', 'default'), args[0], props)

    print()
    print(f"{utils.Colors.BOLD}Running: {args[0]}{utils.Colors.RESET}")
    utils.runCmd(out, *args[1:])
    print()
    print(f"{utils.Colors.GREEN}Process exited with success{utils.Colors.RESET}")


def debugCmd(opts: dict, args: list[str]) -> None:
    props = propsFromOptions(opts)
    if len(args) == 0:
        print(f"Usage: osdk debug <component>")
        sys.exit(1)

    out = build.buildOne(opts.get('target', 'default:debug'), args[0], props)

    print()
    print(f"{utils.Colors.BOLD}Debugging: {args[0]}{utils.Colors.RESET}")
    utils.runCmd("/usr/bin/lldb", "-o", "run",  out, *args[1:])
    print()
    print(f"{utils.Colors.GREEN}Process exited with success{utils.Colors.RESET}")


def buildCmd(opts: dict, args: list[str]) -> None:
    props = propsFromOptions(opts)
    allTargets = opts.get('all-targets', False)
    targetName = opts.get('target', 'default')

    if allTargets:
        for target in targets.available():
            if len(args) == 0:
                build.buildAll(target, props)
            else:
                for component in args:
                    build.buildOne(target, component, props)
    else:
        if len(args) == 0:
            build.buildAll(targetName, props)
        else:
            for component in args:
                build.buildOne(targetName, component, props)


def listCmd(opts: dict, args: list[str]) -> None:
    props = propsFromOptions(opts)
    targetName = opts.get('target', 'default')
    target = targets.load(targetName, props)
    components = manifests.loadAll("src", target)

    print(f"Available components for target '{targetName}':")
    componentsNames = list(components.keys())
    componentsNames.sort()
    for component in componentsNames:
        if components[component]["enabled"]:
            print("  " + component)
    print("")


def cleanCmd(opts: dict, args: list[str]) -> None:
    shutil.rmtree(".osdk/build", ignore_errors=True)


def nukeCmd(opts: dict, args: list[str]) -> None:
    shutil.rmtree(".osdk", ignore_errors=True)


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


def versionCmd(opts: dict, args: list[str]) -> None:
    print("OSDK v" + __version__)


CMDS = {
    "run": {
        "func": runCmd,
        "desc": "Run a component on the host",
    },
    "debug": {
        "func": debugCmd,
        "desc": "Run a component on the host in debug mode",
    },
    "build": {
        "func": buildCmd,
        "desc": "Build one or more components",
    },
    "list": {
        "func": listCmd,
        "desc": "List available components",
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
    "version": {
        "func": versionCmd,
        "desc": "Show current version",
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
