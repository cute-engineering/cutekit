import os
import json
from typing import Optional
from . import model, cli, vt100, jexpr, const


def graph(
    registry: model.Registry,
    target: model.Target,
    scope: Optional[str] = None,
    showExe: bool = True,
    showDisabled: bool = False,
):
    from graphviz import Digraph  # type: ignore

    g = Digraph(target.id, filename="graph.gv")

    g.attr("graph", splines="ortho", rankdir="BT", ranksep="1.5")
    g.attr("node", shape="ellipse")
    g.attr(
        "graph",
        label=f"<<B>{scope or 'Full Dependency Graph'}</B><BR/>{target.id}>",
        labelloc="t",
    )

    scopeInstance = None

    if scope is not None:
        scopeInstance = registry.lookup(scope, model.Component)

    for component in registry.iter(model.Component):
        if not component.type == model.Kind.LIB and not showExe:
            continue

        if (
            scopeInstance is not None
            and component.id != scope
            and component.id not in scopeInstance.resolved[target.id].required
        ):
            continue

        if component.resolved[target.id].enabled:
            fillcolor = "lightgrey" if component.type == model.Kind.LIB else "lightblue"
            shape = "plaintext" if not scope == component.id else "box"

            g.node(
                component.id,
                f"<<B>{component.id}</B><BR/>{vt100.wordwrap(component.description, 40,newline='<BR/>')}>",
                shape=shape,
                style="filled",
                fillcolor=fillcolor,
            )

            for req in component.requires:
                g.edge(component.id, req)

            for req in component.provides:
                isChosen = target.routing.get(req, None) == component.id

                g.edge(
                    req,
                    component.id,
                    arrowhead="none",
                    color=("blue" if isChosen else "black"),
                )
        elif showDisabled:
            g.node(
                component.id,
                f"<<B>{component.id}</B><BR/>{vt100.wordwrap(component.description, 40,newline='<BR/>')}<BR/><BR/><I>{vt100.wordwrap(str(component.resolved[target.id].reason), 40,newline='<BR/>')}</I>>",
                shape="plaintext",
                style="filled",
                fontcolor="#999999",
                fillcolor="#eeeeee",
            )

            for req in component.requires:
                g.edge(component.id, req, color="#aaaaaa")

            for req in component.provides:
                g.edge(req, component.id, arrowhead="none", color="#aaaaaa")

    g.view(filename=os.path.join(target.builddir, "graph.gv"))


class GraphArgs(model.TargetArgs):
    onlyLibs: bool = cli.arg(None, "only-libs", "Show only libraries")
    showDisabled: bool = cli.arg(None, "show-disabled", "Show disabled components")
    scope: str = cli.arg(
        None, "scope", "Show only the specified component and its dependencies"
    )


def codeWorkspace(project: model.Project, registry: model.Registry) -> jexpr.Jexpr:
    workspace = {
        "folders": [],
        "tasks": {
            "version": "2.0.0",
            "tasks": [],
        },
    }

    folders = workspace["folders"]

    def pickEmoji(proj: model.Project) -> str:
        if proj.id == project.id:
            return "🏠"
        return "📦"

    for proj in registry.iter(model.Project):
        name = proj.id.split("/")[-1].replace("-", " ").capitalize()

        folders.append(
            {
                "path": proj.dirname(),
                "name": f"{pickEmoji(proj)} {name}",
            }
        )

    folders.append(
        {
            "name": "⚙️ CuteKit (Project)",
            "path": const.PROJECT_CK_DIR,
        }
    )

    folders.append(
        {
            "name": "⚙️ CuteKit (Global)",
            "path": const.GLOBAL_CK_DIR,
        }
    )

    tasks = workspace["tasks"]["tasks"]

    for comp in registry.iter(model.Component):
        if comp.type != model.Kind.EXE:
            continue

        tasks.append(
            {
                "icon": {"id": "play", "color": "terminal.ansiBlue"},
                "label": f"Run {comp.id}",
                "type": "shell",
                "command": f"ck builder run --mixins=release {comp.id}",
                "problemMatcher": [],
            }
        )

        tasks.append(
            {
                "icon": {"id": "debug", "color": "terminal.ansiGreen"},
                "label": f"Debug {comp.id}",
                "type": "shell",
                "command": f"ck builder run --mixins=release,debug --debug {comp.id}",
                "problemMatcher": [],
            }
        )

    tasks.append(
        {
            "icon": {"id": "gear", "color": "terminal.ansiYellow"},
            "label": "Build Workspace",
            "type": "shell",
            "command": "cutekit builder build",
            "group": {
                "kind": "build",
                "isDefault": True,
            },
        }
    )

    tasks.append(
        {
            "icon": {"id": "sync", "color": "terminal.ansiYellow"},
            "label": "Update Workspace",
            "type": "shell",
            "command": "cutekit export code-workspace --write",
            "problemMatcher": [],
        }
    )

    tasks.append(
        {
            "icon": {"id": "trash", "color": "terminal.ansiRed"},
            "label": "Clean Workspace",
            "type": "shell",
            "command": "cutekit builder clean",
            "problemMatcher": [],
        }
    )

    tasks.append(
        {
            "icon": {"id": "trash", "color": "terminal.ansiRed"},
            "label": "Nuke Workspace",
            "type": "shell",
            "command": "cutekit builder nuke",
            "problemMatcher": [],
        }
    )

    return workspace


def compileFlags(
    lang: str, registry: model.Registry, target: model.Target
) -> list[str]:
    flags = []
    if lang == "c++":
        flags.append("-xc++")

    return flags


@cli.command("e", "export", "Export various artifacts")
def _():
    pass


@cli.command("g", "export/graph", "Show the dependency graph")
def _(args: GraphArgs):
    registry = model.Registry.use(args)
    target = model.Target.use(args)

    graph(
        registry,
        target,
        scope=args.scope,
        showExe=not args.onlyLibs,
        showDisabled=args.showDisabled,
    )


class WorkspaceArgs(model.RegistryArgs):
    open: bool = cli.arg(None, "open", "Open the workspace file in VSCode")
    write: bool = cli.arg(None, "write", "Write the workspace file to disk")


@cli.command("w", "export/code-workspace", "Generate a VSCode workspace file")
def _(args: WorkspaceArgs):
    project = model.Project.use()
    projectName = project.id.split("/")[-1].replace("-", " ").lower()
    registry = model.Registry.use(args)
    j = codeWorkspace(project, registry)

    args.write = args.write or args.open

    if args.write:
        with open(f"{projectName}.code-workspace", "w") as f:
            f.write(json.dumps(j, indent=2))

        print(f"Wrote {projectName}.code-workspace")
    else:
        print(json.dumps(j, indent=2))

    if args.open:
        os.system(f"code {projectName}.code-workspace")


class CompileFlagsArgs(model.TargetArgs):
    lang: str = cli.arg(None, "lang", "The language to generate flags for (c++ or c)")
    write: bool = cli.arg(None, "write", "Write the flags to a file")


@cli.command(
    "c", "export/compile-flags", "Generate compile flags suitable for use with clangd"
)
def _(args: CompileFlagsArgs):
    registry = model.Registry.use(args)
    target = model.Target.use(args)

    if args.write:
        with open("compile-flags.txt", "w") as f:
            f.write("\n".join(compileFlags(args.lang, registry, target)))
    else:
        print("\n".join(compileFlags(args.lang, registry, target)))
