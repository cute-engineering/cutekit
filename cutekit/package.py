from pathlib import Path
from . import cli, model, builder, shell
import os


class PackageArgs(model.TargetArgs):
    component: str = cli.operand("component", "Component to package")
    layout: str = cli.arg(None, "layout", "Installation layout")
    sysroot: str = cli.arg(None, "sysroot", "System root directory", "/")


def package(args: PackageArgs):
    args.sysroot = os.path.abspath(args.sysroot or "/")

    dest = Path(args.sysroot) / Path(args.prefix).relative_to("/")

    registry = model.Registry.use(args)
    toInstall = registry.lookup(args.component, model.Component)
    if not toInstall:
        raise RuntimeError(f"Component {args.component} not found")
    target = model.Target.use(args)
    scope = builder.TargetScope(registry, target)

    products = []

    for c in toInstall.resolved[target.id].required:
        print(f"Building {c}...")
        component = registry.lookup(c, model.Component)
        assert component, f"Component {args.component} not found"
        products += builder.build(scope, [component])

    print(f"Installing to {dest}...")
    print(f"sysroot: {args.sysroot}")
    print(f"prefix: {args.prefix}")

    print("")

    shell.mkdir(str(dest / "bin"))
    shell.mkdir(str(dest / "share"))
    for product in products:
        toInstall = product.component
        print(f"Installing {toInstall.id}...")
        if toInstall.type == model.Kind.EXE:
            name = toInstall.id
            name = name.removesuffix(".main").removesuffix(".cli")
            shell.cp(str(product.path), str(dest / "bin" / name))

        ressources = builder.listRes(toInstall)
        if ressources:
            shell.mkdir(str(dest / "share" / toInstall.id))
            for res in builder.listRes(toInstall):
                rel = Path(res).relative_to(toInstall.subpath("res"))
                resDest = dest / "share" / toInstall.id / rel
                resDest.parent.mkdir(parents=True, exist_ok=True)
                shell.cp(str(res), str(resDest))


# MARK: Commands ---------------------------------------------------------------


@cli.command("package", "Package a component for installation")
def _(args: PackageArgs):
    package(args)
