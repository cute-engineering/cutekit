from graphviz import Digraph

from osdk.context import Context


def view(context: Context, showExe: bool = False):
    g = Digraph(context.target.id, filename='graph.gv')

    g.attr('graph',  splines='ortho', concentrate='true')
    g.attr('node', shape='ellipse')

    for instance in context.instances:
        if not instance.isLib() and not showExe:
            continue

        g.node(instance.manifest.id, f"<<B>{instance.manifest.id}</B><BR/>{instance.manifest.decription}>",
               shape="plaintext", style="filled", fillcolor="lightgrey" if instance.isLib() else "lightblue")

        for req in instance.manifest.requires:
            g.edge(instance.manifest.id, req)

        for req in instance.manifest.provides:
            g.edge(req, instance.manifest.id)

    g.view(filename=f"{context.builddir()}/graph.gv")
