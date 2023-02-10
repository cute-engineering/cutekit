from typing import Callable, cast

from osdk.args import Args
from osdk.context import contextFor
from osdk import context, shell, const, vt100, builder, graph

Callback = Callable[[Args], None]


class Cmd:
    shortName: str
    longName: str
    helpText: str
    callback: Callable[[Args], None]
    isPlugin: bool = False

    def __init__(self, shortName: str, longName: str, helpText: str, callback: Callable[[Args], None]):
        self.shortName = shortName
        self.longName = longName
        self.helpText = helpText
        self.callback = callback


cmds: list[Cmd] = []


def append(cmd: Cmd):
    cmd.isPlugin = True
    cmds.append(cmd)
    cmds.sort(key=lambda c: c.shortName)


def runCmd(args: Args):
    targetSpec = cast(str, args.consumeOpt(
        "target", "host-" + shell.uname().machine))

    componentSpec = args.consumeArg()

    if componentSpec is None:
        raise Exception("Component not specified")

    exe = builder.build(componentSpec, targetSpec)

    shell.exec(exe)


cmds += [Cmd("r", "run", "Run the target", runCmd)]


def debugCmd(args: Args):
    targetSpec = cast(str, args.consumeOpt(
        "target", "host-" + shell.uname().machine))

    componentSpec = args.consumeArg()

    if componentSpec is None:
        raise Exception("Component not specified")

    exe = builder.build(componentSpec, targetSpec)

    shell.exec("/usr/bin/lldb", "-o", "run", exe)


cmds += [Cmd("d", "debug", "Debug the target", debugCmd)]


def buildCmd(args: Args):
    targetSpec = cast(str, args.consumeOpt(
        "target", "host-" + shell.uname().machine))

    componentSpec = args.consumeArg()

    if componentSpec is None:
        raise Exception("Component not specified")

    builder.build(componentSpec, targetSpec)


cmds += [Cmd("b", "build", "Build the target", buildCmd)]


def listCmd(args: Args):
    components = context.loadAllComponents()
    targets = context.loadAllTargets()

    vt100.title("Components")
    if len(components) == 0:
        print(f"   (No components available)")
    else:
        print(vt100.indent(vt100.wordwrap(
            ", ".join(map(lambda m: m.id, components)))))
    print()

    vt100.title("Targets")

    if len(targets) == 0:
        print(f"   (No targets available)")
    else:
        print(vt100.indent(vt100.wordwrap(", ".join(map(lambda m: m.id, targets)))))

    print()


cmds += [Cmd("l", "list", "List the targets", listCmd)]


def cleanCmd(args: Args):
    shell.rmrf(const.BUILD_DIR)


cmds += [Cmd("c", "clean", "Clean the build directory", cleanCmd)]


def nukeCmd(args: Args):
    shell.rmrf(const.OSDK_DIR)


cmds += [Cmd("n", "nuke", "Clean the build directory and cache", nukeCmd)]


def helpCmd(args: Args):
    usage()

    print()

    vt100.title("Description")
    print("    Operating System Development Kit.")

    print()
    vt100.title("Commands")
    for cmd in cmds:
        pluginText = ""
        if cmd.isPlugin:
            pluginText = f"{vt100.CYAN}(plugin){vt100.RESET}"

        print(
            f" {vt100.GREEN}{cmd.shortName}{vt100.RESET}  {cmd.longName} - {cmd.helpText} {pluginText}")

    print()


cmds += [Cmd("h", "help", "Show this help message", helpCmd)]


def versionCmd(args: Args):
    print(f"OSDK v{const.VERSION}\n")


cmds += [Cmd("v", "version", "Show current version", versionCmd)]


def graphCmd(args: Args):
    targetSpec = cast(str, args.consumeOpt(
        "target", "host-" + shell.uname().machine))

    scope: str | None = cast(str | None, args.tryConsumeOpt("scope"))
    onlyLibs: bool = args.consumeOpt("only-libs", False) == True
    showDisabled: bool = args.consumeOpt("show-disabled", False) == True

    context = contextFor(targetSpec)

    graph.view(context, scope=scope, showExe=not onlyLibs,
               showDisabled=showDisabled)


cmds += [Cmd("g", "graph", "Show dependency graph", graphCmd)]


def usage():
    print(f"Usage: {const.ARGV0} <command> [args...]")


def exec(args: Args):
    cmd = args.consumeArg()

    if cmd is None:
        raise Exception("No command specified")

    for c in cmds:
        if c.shortName == cmd or c.longName == cmd:
            c.callback(args)
            return

    raise Exception(f"Unknown command {cmd}")
