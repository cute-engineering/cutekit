import os
import json
import logging
import tempfile
import requests
import sys

from typing import Callable, cast

from cutekit import context, shell, const, vt100, builder, graph, project
from cutekit.args import Args
from cutekit.model import Extern
from cutekit.context import contextFor

Callback = Callable[[Args], None]

logger = logging.getLogger(__name__)


class Cmd:
    shortName: str | None
    longName: str
    helpText: str
    callback: Callable[[Args], None]
    isPlugin: bool = False

    def __init__(self, shortName: str | None, longName: str, helpText: str, callback: Callable[[Args], None]):
        self.shortName = shortName
        self.longName = longName
        self.helpText = helpText
        self.callback = callback


cmds: list[Cmd] = []


def append(cmd: Cmd):
    cmd.isPlugin = True
    cmds.append(cmd)
    cmds.sort(key=lambda c: c.shortName or c.longName)


def runCmd(args: Args):
    project.chdir()

    targetSpec = cast(str, args.consumeOpt(
        "target", "host-" + shell.uname().machine))

    componentSpec = args.consumeArg()

    if componentSpec is None:
        raise RuntimeError("Component not specified")

    component = builder.build(componentSpec, targetSpec)

    os.environ["CK_TARGET"] = component.context.target.id
    os.environ["CK_COMPONENT"] = component.id()
    os.environ["CK_BUILDDIR"] = component.context.builddir()

    shell.exec(component.outfile(), *args.args)


cmds += [Cmd("r", "run", "Run the target", runCmd)]


def testCmd(args: Args):
    project.chdir()

    targetSpec = cast(str, args.consumeOpt(
        "target", "host-" + shell.uname().machine))
    builder.testAll(targetSpec)


cmds += [Cmd("t", "test", "Run all test targets", testCmd)]


def debugCmd(args: Args):
    project.chdir()

    targetSpec = cast(str, args.consumeOpt(
        "target", "host-" + shell.uname().machine))

    componentSpec = args.consumeArg()

    if componentSpec is None:
        raise RuntimeError("Component not specified")

    component = builder.build(componentSpec, targetSpec)

    os.environ["CK_TARGET"] = component.context.target.id
    os.environ["CK_COMPONENT"] = component.id()
    os.environ["CK_BUILDDIR"] = component.context.builddir()

    shell.exec("lldb", "-o", "run", component.outfile(), *args.args)


cmds += [Cmd("d", "debug", "Debug the target", debugCmd)]


def buildCmd(args: Args):
    project.chdir()

    targetSpec = cast(str, args.consumeOpt(
        "target", "host-" + shell.uname().machine))

    componentSpec = args.consumeArg()

    if componentSpec is None:
        builder.buildAll(targetSpec)
    else:
        builder.build(componentSpec, targetSpec)


cmds += [Cmd("b", "build", "Build the target", buildCmd)]


def listCmd(args: Args):
    project.chdir()

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
    project.chdir()
    shell.rmrf(const.BUILD_DIR)


cmds += [Cmd("c", "clean", "Clean the build directory", cleanCmd)]


def nukeCmd(args: Args):
    project.chdir()
    shell.rmrf(const.PROJECT_CK_DIR)


cmds += [Cmd("n", "nuke", "Clean the build directory and cache", nukeCmd)]


def helpCmd(args: Args):
    usage()

    print()

    vt100.title("Description")
    print(f"    {const.DESCRIPTION}")

    print()
    vt100.title("Commands")
    for cmd in cmds:
        pluginText = ""
        if cmd.isPlugin:
            pluginText = f"{vt100.CYAN}(plugin){vt100.RESET}"

        print(
            f" {vt100.GREEN}{cmd.shortName or ' '}{vt100.RESET}  {cmd.longName} - {cmd.helpText} {pluginText}")

    print()
    vt100.title("Logging")
    print(f"    Logs are stored in:")
    print(f"     - {const.PROJECT_LOG_FILE}")
    print(f"     - {const.GLOBAL_LOG_FILE}")


cmds += [Cmd("h", "help", "Show this help message", helpCmd)]


def versionCmd(args: Args):
    print(f"CuteKit v{const.VERSION_STR}\n")


cmds += [Cmd("v", "version", "Show current version", versionCmd)]


def graphCmd(args: Args):
    project.chdir()

    targetSpec = cast(str, args.consumeOpt(
        "target", "host-" + shell.uname().machine))

    scope: str | None = cast(str | None, args.tryConsumeOpt("scope"))
    onlyLibs: bool = args.consumeOpt("only-libs", False) == True
    showDisabled: bool = args.consumeOpt("show-disabled", False) == True

    context = contextFor(targetSpec)

    graph.view(context, scope=scope, showExe=not onlyLibs,
               showDisabled=showDisabled)


cmds += [Cmd("g", "graph", "Show dependency graph", graphCmd)]


def grabExtern(extern: dict[str, Extern]):
    for extSpec, ext in extern.items():
        extPath = os.path.join(const.EXTERN_DIR, extSpec)

        if os.path.exists(extPath):
            print(f"Skipping {extSpec}, already installed")
            continue

        print(f"Installing {extSpec}-{ext.tag} from {ext.git}...")
        shell.popen("git", "clone", "--depth", "1", "--branch",
                    ext.tag, ext.git, extPath)
        
        if os.path.exists(os.path.join(extPath, "project.json")):
            grabExtern(context.loadProject(extPath).extern)


def installCmd(args: Args):
    project.chdir()

    pj = context.loadProject(".")
    grabExtern(pj.extern)


cmds += [Cmd("i", "install", "Install all the external packages", installCmd)]


def initCmd(args: Args):
    template = args.consumeArg()

    if template is None:
        raise RuntimeError("No template was provided")

    repo = const.DEFAULT_REPO_TEMPLATES if not "repo" in args.opts else args.opts["repo"]
    list = "list" in args.opts

    if list:
        logger.info("Fetching registry...")
        r = requests.get(
            f'https://raw.githubusercontent.com/{repo}/main/registry.json')

        if r.status_code != 200:
            logger.error('Failed to fetch registry')
            exit(1)

        print('\n'.join(
            f"* {entry['id']} - {entry['description']}" for entry in json.loads(r.text)))
    else:
        with tempfile.TemporaryDirectory() as tmp:
            shell.exec(*["git", "clone", "-n", "--depth=1",
                       "--filter=tree:0", f"https://github.com/{repo}", tmp, "-q"])
            shell.exec(*["git", "-C", tmp, "sparse-checkout",
                       "set", "--no-cone", template, "-q"])
            shell.exec(*["git", "-C", tmp, "checkout", "-q"])
            shell.mv(os.path.join(tmp, template), os.path.join(".", template))


cmds += [Cmd("I", "init", "Initialize a new project", initCmd)]


def usage():
    print(f"Usage: {const.ARGV0} <command> [args...]")


def error(msg: str) -> None:
    print(f"{vt100.RED}Error:{vt100.RESET} {msg}\n", file=sys.stderr)


def exec(args: Args):
    cmd = args.consumeArg()

    if cmd is None:
        raise RuntimeError("No command specified")

    for c in cmds:
        if c.shortName == cmd or c.longName == cmd:
            c.callback(args)
            return

    raise RuntimeError(f"Unknown command {cmd}")
