from typing import Callable, cast
import os
import json

from osdk.args import Args
from osdk.context import contextFor
from osdk import context, shell, const, vt100, builder, graph

Callback = Callable[[Args], None]


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

    shell.exec("lldb", "-o", "run", exe)


cmds += [Cmd("d", "debug", "Debug the target", debugCmd)]


def buildCmd(args: Args):
    targetSpec = cast(str, args.consumeOpt(
        "target", "host-" + shell.uname().machine))

    componentSpec = args.consumeArg()

    if componentSpec is None:
        builder.buildAll(targetSpec)
    else:
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
            f" {vt100.GREEN}{cmd.shortName or ' '}{vt100.RESET}  {cmd.longName} - {cmd.helpText} {pluginText}")

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


def installCmd(args: Args):
    project = context.loadProject(".")

    for extSpec in project.extern:
        ext = project.extern[extSpec]

        extPath = os.path.join(const.EXTERN_DIR, extSpec)

        if os.path.exists(extPath):
            print(f"Skipping {extSpec}, already installed")
            continue

        print(f"Installing {extSpec}-{ext.tag} from {ext.git}...")
        shell.popen("git", "clone", "--depth", "1", "--branch",
                    ext.tag, ext.git, extPath)


cmds += [Cmd("i", "install", "Install all the external packages", installCmd)]


def initCmd(args: Args):
    """
    |
    | - project.json
    | - src/
    |   | - project_name/
    |       | - main.c
    |       | - manifest.json
    | - meta/
    |   | - targets/
    |   |   | - host-*.json
    |   | - plugins/
    |   |   | - run.py
    | - .gitignore
    | - README.md
    |
    """

    print("This utility will walk you through creating a new project.")
    print("This only covers the most common items, and tries to give sensible defaults.")
    print()
    print("First, let's create a project.json file.")

    project_name = input("Project name: ")
    description = input("Description: ")

    to_create = ["src", "meta", os.path.join("meta", "targets"), os.path.join("meta", "plugins")]

    os.mkdir(project_name.lower())
    for directory in to_create:
        os.mkdir(os.path.join(project_name.lower(), directory))

    with open(os.path.join(project_name.lower(), "project.json"), "w") as f:
        f.write(json.dumps({
            "$schema": "https://schemas.cute.engineering/latest/osdk.manifest.component",
            "name": project_name,
            "type": "project",
            "description": description,
            "extern": {},
        }, indent=4))

    with open(os.path.join(project_name.lower(), ".gitignore"), "w") as f:
        f.write(".osdk\n.ninja_log\n__pycache__\n")

    with open(os.path.join(project_name.lower(), "README.md"), "w") as f:
        f.write(f"# {project_name}\n")
        f.write("I was created using the OSDK!\n")
        f.write(
            "You can find more information about the OSDK in its [Repo](https://github.com/cute-engineering/osdk)."
        )

    with open(os.path.join(project_name.lower(), "src", "main.c"), "w") as f:
        f.write("#include <stdio.h>\n\n")
        f.write("int main(void)\n{\n")
        f.write("    printf(\"Hello, World!\\n\");\n")
        f.write("    return 0;\n")
        f.write("}")

    with open(os.path.join(project_name.lower(), "src", "manifest.json"), "w") as f:
        f.write(json.dumps({
            "$schema": "https://schemas.cute.engineering/latest/osdk.manifest.component",
            "id": project_name.lower(),
            "type": "exe",
            "description": description,
        }, indent=4))

    with open(os.path.join(project_name.lower(), "meta", "plugins", "run.py"), "w") as f:
        f.write("from osdk import builder, shell\n")
        f.write("from osdk.args import Args\n")
        f.write("from osdk.cmds import Cmd, append\n\n")
        f.write("def runCmd(args: Args) -> None:\n")
        f.write(
            f"    {project_name.lower()} = builder.build(\"{project_name.lower()}\", \"host-{shell.uname().machine}\")\n"
        )
        f.write(f"    shell.exec(*[{project_name.lower()}])")
        f.write("\n\nappend(Cmd(\"s\", \"start\", \"Run the project\", runCmd))")

    with open(os.path.join(project_name.lower(), "meta", "targets", f"host-{shell.uname().machine}.json"), "w") as f:
        f.write(json.dumps({
            "$schema": "https://schemas.cute.engineering/latest/osdk.manifest.component",
            "id": f"host-{shell.uname().machine}",
            "type": "target",
            "props": {
                "arch": shell.uname().machine,
                "toolchain": "clang",
                "sys": [
                    "@uname",
                    "sysname"
                ],
                "abi": "unknown",
                "freestanding": False,
                "host": True,
            },
            "tools": {
                "cc": {
                    "cmd": [
                        "@latest",
                        "clang"
                    ],
                    "args": []
                },
                "cxx": {
                    "cmd": [
                        "@latest",
                        "clang++"
                    ],
                    "args": []
                },
                "ld": {
                    "cmd": [
                        "@latest",
                        "clang++"
                    ],
                    "args": [
                    ]
                },
                "ar": {
                    "cmd": [
                        "@latest",
                        "llvm-ar"
                    ],
                    "args": [
                        "rcs"
                    ]
                },
                "as": {
                    "cmd": "clang",
                    "args": [
                        "-c"
                    ]
                }
            }
        }, indent=4))

        shell.exec(*["git", "init", project_name.lower()])
        print("Done! Don't forget to add a LICENSE ;)")


cmds += [Cmd("I", "init", "Start a new project", initCmd)]


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
