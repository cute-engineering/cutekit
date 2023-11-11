import logging
import os
import sys


from cutekit import (
    context,
    shell,
    const,
    vt100,
    builder,
    project,
    cli,
    model,
    jexpr,
)


_logger = logging.getLogger(__name__)


@cli.command("p", "project", "Show project information")
def runCmd(args: cli.Args):
    project.chdir()

    targetSpec = str(args.consumeOpt("target", "host-" + shell.uname().machine))
    props = args.consumePrefix("prop:")

    componentSpec = args.consumeArg()

    if componentSpec is None:
        raise RuntimeError("Component not specified")

    component = builder.build(componentSpec, targetSpec, props)

    os.environ["CK_TARGET"] = component.context.target.id
    os.environ["CK_COMPONENT"] = component.id()
    os.environ["CK_BUILDDIR"] = component.context.builddir()

    shell.exec(component.outfile(), *args.args)


@cli.command("t", "test", "Run all test targets")
def testCmd(args: cli.Args):
    project.chdir()

    targetSpec = str(args.consumeOpt("target", "host-" + shell.uname().machine))
    builder.testAll(targetSpec)


@cli.command("d", "debug", "Debug a component")
def debugCmd(args: cli.Args):
    project.chdir()

    targetSpec = str(args.consumeOpt("target", "host-" + shell.uname().machine))
    props = args.consumePrefix("prop:")

    componentSpec = args.consumeArg()

    if componentSpec is None:
        raise RuntimeError("Component not specified")

    component = builder.build(componentSpec, targetSpec, props)

    os.environ["CK_TARGET"] = component.context.target.id
    os.environ["CK_COMPONENT"] = component.id()
    os.environ["CK_BUILDDIR"] = component.context.builddir()

    shell.exec("lldb", "-o", "run", component.outfile(), *args.args)


@cli.command("b", "build", "Build a component or all components")
def buildCmd(args: cli.Args):
    project.chdir()

    targetSpec = str(args.consumeOpt("target", "host-" + shell.uname().machine))
    props = args.consumePrefix("prop:")
    componentSpec = args.consumeArg()

    if componentSpec is None:
        builder.buildAll(targetSpec, props)
    else:
        builder.build(componentSpec, targetSpec, props)


@cli.command("l", "list", "List all components and targets")
def listCmd(args: cli.Args):
    project.chdir()

    components = context.loadAllComponents()
    targets = context.loadAllTargets()

    vt100.title("Components")
    if len(components) == 0:
        print("   (No components available)")
    else:
        print(vt100.indent(vt100.wordwrap(", ".join(map(lambda m: m.id, components)))))
    print()

    vt100.title("Targets")

    if len(targets) == 0:
        print("   (No targets available)")
    else:
        print(vt100.indent(vt100.wordwrap(", ".join(map(lambda m: m.id, targets)))))

    print()


@cli.command("c", "clean", "Clean build files")
def cleanCmd(args: cli.Args):
    project.chdir()
    shell.rmrf(const.BUILD_DIR)


@cli.command("n", "nuke", "Clean all build files and caches")
def nukeCmd(args: cli.Args):
    project.chdir()
    shell.rmrf(const.PROJECT_CK_DIR)


@cli.command("h", "help", "Show this help message")
def helpCmd(args: cli.Args):
    usage()

    print()

    vt100.title("Description")
    print(f"    {const.DESCRIPTION}")

    print()
    vt100.title("Commands")
    for cmd in cli.commands:
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


@cmd("v", "version", "Show current version")
def versionCmd(args: cli.Args):
    print(f"CuteKit v{const.VERSION_STR}")


def grabExtern(extern: dict[str, model.Extern]):
    for extSpec, ext in extern.items():
        extPath = os.path.join(const.EXTERN_DIR, extSpec)

        if os.path.exists(extPath):
            print(f"Skipping {extSpec}, already installed")
            continue

        print(f"Installing {extSpec}-{ext.tag} from {ext.git}...")
        shell.popen(
            "git", "clone", "--depth", "1", "--branch", ext.tag, ext.git, extPath
        )

        if os.path.exists(os.path.join(extPath, "project.json")):
            grabExtern(context.loadProject(extPath).extern)


@cli.command("i", "install", "Install required external packages")
def installCmd(args: cli.Args):
    project.chdir()

    pj = context.loadProject(".")
    grabExtern(pj.extern)


@cli.command("I", "init", "Initialize a new project")
def initCmd(args: cli.Args):
    import requests

    repo = args.consumeOpt("repo", const.DEFAULT_REPO_TEMPLATES)
    list = args.consumeOpt("list")

    template = args.consumeArg()
    name = args.consumeArg()

    _logger.info("Fetching registry...")
    r = requests.get(f"https://raw.githubusercontent.com/{repo}/main/registry.json")

    if r.status_code != 200:
        _logger.error("Failed to fetch registry")
        exit(1)

    registry = r.json()

    if list:
        print(
            "\n".join(f"* {entry['id']} - {entry['description']}" for entry in registry)
        )
        return

    if not template:
        raise RuntimeError("Template not specified")

    def template_match(t: jexpr.Json) -> str:
        return t["id"] == template

    if not any(filter(template_match, registry)):
        raise LookupError(f"Couldn't find a template named {template}")

    if not name:
        _logger.info(f"No name was provided, defaulting to {template}")
        name = template

    if os.path.exists(name):
        raise RuntimeError(f"Directory {name} already exists")

    print(f"Creating project {name} from template {template}...")
    shell.cloneDir(f"https://github.com/{repo}", template, name)
    print(f"Project {name} created\n")

    print("We suggest that you begin by typing:")
    print(f"  {vt100.GREEN}cd {name}{vt100.RESET}")
    print(
        f"  {vt100.GREEN}cutekit install{vt100.BRIGHT_BLACK} # Install external packages{vt100.RESET}"
    )
    print(
        f"  {vt100.GREEN}cutekit build{vt100.BRIGHT_BLACK}  # Build the project{vt100.RESET}"
    )


def usage():
    print(f"Usage: {const.ARGV0} <command> [args...]")


def error(msg: str) -> None:
    print(f"{vt100.RED}Error:{vt100.RESET} {msg}\n", file=sys.stderr)


def exec(args: cli.Args):
    cmd = args.consumeArg()

    if cmd is None:
        raise RuntimeError("No command specified")

    for c in cli.commands:
        if c.shortName == cmd or c.longName == cmd:
            c.callback(args)
            return

    raise RuntimeError(f"Unknown command {cmd}")
