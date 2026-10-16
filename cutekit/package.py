from pathlib import Path
from . import cli, model, builder, shell, utils
import os
import tempfile


class InstallArgs(model.TargetArgs):
    component: str = cli.operand("component", "Component to package")
    staging: str = cli.arg(None, "staging", "Staging directory for installation", default="/")



def install(args: InstallArgs) -> tuple[model.Project, builder.ComponentScope]:
    args.staging = os.path.abspath(args.staging or "/")

    dest = Path(args.staging) / Path(args.prefix).relative_to("/")

    registry = model.Registry.use(args)
    project = model.Project.ensure()
    component = registry.ensure(args.component, model.Component)
    target = model.Target.use(args)
    scope = builder.TargetScope(registry, target)

    print("Building...")
    components = [component] + [registry.ensure(c, model.Component) for c in component.resolved[target.id].required]
    products = builder.build(scope, components)

    print(f"Installing to {dest}...")
    print(f"staging: {args.staging}")
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

    return project, scope.openComponentScope(component)


@cli.command("install", "Install a component to the sysroot")
def _(args: InstallArgs):
    install(args)


# MARK: Packaging --------------------------------------------------------------

class PackageArgs(InstallArgs):
    layout: str = cli.arg(None, "layout", "Installation layout")
    output: str = cli.arg(None, "output", "Output package file")
    maintainer : str = cli.arg(None, "maintainer", "Maintainer of the package")
    depends: list[str] = cli.arg(None, "depends", "Dependencies of the package", default=[])

def packageFlat(project: model.Project, scope : builder.ComponentScope, args : PackageArgs):
    # NOTE: -a picks the compression from the output suffix (.tar.gz, .tar.zst, ...)
    shell.exec("tar", "-C", args.staging, "-caf", args.output, ".")

def debianDepends(args: PackageArgs) -> list[str]:
    binDir = Path(args.staging) / Path(args.prefix).relative_to("/") / "bin"
    exes = sorted(str(p) for p in binDir.iterdir() if p.is_file()) if binDir.exists() else []
    if not exes:
        return []

    # NOTE: dpkg-shlibdeps insists on running next to a debian/control file,
    #       even though it doesn't need anything from it.
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "debian").mkdir()
        (Path(tmp) / "debian" / "control").touch()
        out = shell.popen("dpkg-shlibdeps", "-O", *exes, cwd=tmp)

    for line in out.splitlines():
        if line.startswith("shlibs:Depends="):
            return [d.strip() for d in line.removeprefix("shlibs:Depends=").split(",") if d.strip()]
    return []


def packageDebian(project: model.Project, scope : builder.ComponentScope, args : PackageArgs):
    arch = scope.target.props["arch"]
    if arch == "x86_64":
        arch = "amd64"

    depends = utils.uniqPreserveOrder(args.depends + debianDepends(args))

    control = f"""
Package: {scope.component.id}
Description: {scope.component.description}
Version: {project.version[1:]}
Section: utils
Priority: optional
Architecture: {arch}
Maintainer: {args.maintainer}
"""
    if depends:
        control += f"Depends: {', '.join(depends)}\n"

    controlFile = Path(args.staging) / "DEBIAN" / "control"
    controlFile.parent.mkdir(parents=True, exist_ok=True)
    controlFile.write_text(f"{control.strip()}\n")
    shell.exec("dpkg-deb", "--build", args.staging, args.output)


LAYOUTS = {
    "flat": packageFlat,
    "deb": packageDebian,
}

@cli.command("package", "Package a component into a tarball")
def _(args : PackageArgs):
    project, scope = install(args)
    layout = args.layout or "flat"
    if layout not in LAYOUTS:
        raise ValueError(f"Unknown layout: {layout}")
    LAYOUTS[layout](project, scope, args)
