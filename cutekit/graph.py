import os

from typing import cast
from . import vt100, context, project, cli, shell


def view(
    context: context.Context,
    scope: str | None = None,
    showExe: bool = True,
    showDisabled: bool = False,
):
    from graphviz import Digraph

    g = Digraph(context.target.id, filename="graph.gv")

    g.attr("graph", splines="ortho", rankdir="BT", ranksep="1.5")
    g.attr("node", shape="ellipse")
    g.attr(
        "graph",
        label=f"<<B>{scope or 'Full Dependency Graph'}</B><BR/>{context.target.id}>",
        labelloc="t",
    )

    scopeInstance = None

    if scope is not None:
        scopeInstance = context.componentByName(scope)

    for instance in context.instances:
        if not instance.isLib() and not showExe:
            continue

        if (
            scopeInstance is not None
            and instance.manifest.id != scope
            and instance.manifest.id not in scopeInstance.resolved
        ):
            continue

        if instance.enabled:
            fillcolor = "lightgrey" if instance.isLib() else "lightblue"
            shape = "plaintext" if not scope == instance.manifest.id else "box"

            g.node(
                instance.manifest.id,
                f"<<B>{instance.manifest.id}</B><BR/>{vt100.wordwrap(instance.manifest.decription, 40,newline='<BR/>')}>",
                shape=shape,
                style="filled",
                fillcolor=fillcolor,
            )

            for req in instance.manifest.requires:
                g.edge(instance.manifest.id, req)

            for req in instance.manifest.provides:
                isChosen = context.target.routing.get(req, None) == instance.manifest.id

                g.edge(
                    req,
                    instance.manifest.id,
                    arrowhead="none",
                    color=("blue" if isChosen else "black"),
                )
        elif showDisabled:
            g.node(
                instance.manifest.id,
                f"<<B>{instance.manifest.id}</B><BR/>{vt100.wordwrap(instance.manifest.decription, 40,newline='<BR/>')}<BR/><BR/><I>{vt100.wordwrap(instance.disableReason, 40,newline='<BR/>')}</I>>",
                shape="plaintext",
                style="filled",
                fontcolor="#999999",
                fillcolor="#eeeeee",
            )

            for req in instance.manifest.requires:
                g.edge(instance.manifest.id, req, color="#aaaaaa")

            for req in instance.manifest.provides:
                g.edge(req, instance.manifest.id, arrowhead="none", color="#aaaaaa")

    g.view(filename=os.path.join(context.builddir(), "graph.gv"))


@cli.command("g", "graph", "Show the dependency graph")
def graphCmd(args: cli.Args):
    project.chdir()

    targetSpec = str(args.consumeOpt("target", "host-" + shell.uname().machine))

    scope: str | None = cast(str | None, args.tryConsumeOpt("scope"))
    onlyLibs: bool = args.consumeOpt("only-libs", False) is True
    showDisabled: bool = args.consumeOpt("show-disabled", False) is True

    ctx = context.contextFor(targetSpec)

    view(ctx, scope=scope, showExe=not onlyLibs, showDisabled=showDisabled)
