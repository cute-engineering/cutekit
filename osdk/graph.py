from graphviz import Digraph

from osdk.context import Context


def view(context: Context):
    g = Digraph(context.target.id, filename='graph.gv')
    
    g.attr('node', shape='ellipse')

    for instance in context.instances:
        if not instance.isLib():
            continue
        g.node(instance.manifest.id, f"<<B>{instance.manifest.id}</B><BR/>{instance.manifest.decription}>",
               shape="plaintext", style="filled")
        for req in instance.manifest.requires:
            g.edge(req, instance.manifest.id)

        for req in instance.manifest.provides:
            g.edge(instance.manifest.id, req)

    g.view(filename=f"{context.builddir()}/graph.gv")
