import os
import json
from typing import Optional
from . import model, cli, vt100, jexpr


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
    j: jexpr.Jexpr = {"folders": []}

    def pickEmoji(proj: model.Project) -> str:
        if proj.id == project.id:
            return "🏠"
        return "📦"

    for proj in registry.iter(model.Project):
        name = proj.id.split("/")[-1].replace("-", " ").capitalize()

        j["folders"].append(
            {
                "path": proj.dirname(),
                "name": f"{pickEmoji(proj)} {name}",
            }
        )

    return j


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


@cli.command("w", "export/code-workspace", "Generate a VSCode workspace file")
def _(args: WorkspaceArgs):
    project = model.Project.use()
    registry = model.Registry.use(args)
    j = codeWorkspace(project, registry)
    if args.open:
        with open("workspace.code-workspace", "w") as f:
            f.write(json.dumps(j, indent=2))
        os.system("code workspace.code-workspace")
    else:
        print(json.dumps(j, indent=2))
