from graphviz import Digraph

from osdk.context import Context
from osdk import vt100


def view(context: Context, scope: str | None = None, showExe: bool = True):
    g = Digraph(context.target.id, filename='graph.gv')

    g.attr('graph',  splines='ortho', rankdir='BT')
    g.attr('node', shape='ellipse')
    g.attr(
        'graph', label=f"<<B>{scope or 'Full Dependency Graph'}</B><BR/>{context.target.id}>", labelloc='t')

    scopeInstance = None

    if scope is not None:
        scopeInstance = context.componentByName(scope)

    for instance in context.instances:
        if not instance.isLib() and not showExe:
            continue

        if scopeInstance is not None and \
            instance.manifest.id != scope and \
                instance.manifest.id not in scopeInstance.resolved:
            continue

        fillcolor = "lightgrey" if instance.isLib() else "lightblue"
        shape = "plaintext" if not scope == instance.manifest.id else 'box'

        g.node(instance.manifest.id, f"<<B>{instance.manifest.id}</B><BR/>{vt100.wordwrap(instance.manifest.decription, 40,newline='<BR/>')}>",
               shape=shape, style="filled", fillcolor=fillcolor)

        for req in instance.manifest.requires:
            g.edge(instance.manifest.id, req)

        for req in instance.manifest.provides:
            g.edge(req, instance.manifest.id, arrowhead="none")

    g.view(filename=f"{context.builddir()}/graph.gv")
