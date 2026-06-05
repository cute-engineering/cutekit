from pathlib import Path
from . import cli, model, builder, shell, const
import os
from typing import Optional, override
import dataclasses as dt

@dt.dataclass(frozen=True)
class PackageSpec:
    dep : Optional[str] = None
    buildDep: Optional[str] = None


@dt.dataclass(frozen=True)
class Package:
    distro: "Distro"
    project: model.Project
    target: model.Target
    component: model.Component
    maintainer: Optional[str] = None

    def name(self) -> str:
        return f"{self.component.id}_{self.project.version}_{self.distro.family}_{self.distro.version}_{self.target.props['arch']}"
    
    def sysroot(self) -> Path:
        return Path(const.PROJECT_CK_DIR) / "sysroot" / self.name()

@dt.dataclass(frozen=True)
class PackageFormat:
    name : str
    def package(self, package: Package, out : Optional[Path] = None) -> Path:
        ...

@dt.dataclass
class PackageManager:
    pass

    def init(self):
        pass

    def install(self, packages: list[PackageSpec]):
        ...

    def installCommand(self, path: Path) -> list[str]:
        ...

@dt.dataclass
class Apt(PackageManager):
    @override
    def init(self):
        shell.exec("apt-get", "update")

    @override
    def install(self, packages: list[PackageSpec]):
        # Install all build deps first
        buildDeps = [p.buildDep for p in packages if p.buildDep]
        if buildDeps:
            shell.exec("apt-get", "install", "-y", *buildDeps)

        # Then install regular deps
        deps = [p.dep for p in packages if p.dep]
        if deps:
            shell.exec("apt-get", "install", "-y", *deps)

    @override
    def installCommand(self, path: Path) -> list[str]:
        return ["apt-get", "install", "-y", str(path)]

class Deb(PackageFormat):
    def __init__(self):
        super().__init__("deb")

    @override
    def package(self, package: Package, out : Optional[Path] = None) -> Path:
        if out is None:
            out = Path(const.PROJECT_CK_DIR) / "dist" / f"{package.name()}.deb"

        # Create control file
        control = package.sysroot() / "DEBIAN" / "control"

        control.parent.mkdir(parents=True)
        control.write_text(f"""Package: {name}
Version: {package.project.version[1:]}
Architecture: {package.target.props['arch']}
Maintainer: {package.maintainer or "Unknown"}
Description: {package.project.description}
""")

        # Create the deb package
        shell.exec("dpkg-deb", "--build", str(package.sysroot()), str(out))

        return out

@dt.dataclass(frozen=True)
class Distro:
    family: str
    version: str
    packages: dict[str, list[PackageSpec]] = dt.field(default_factory=dict)



    def packageFormat(self) -> PackageFormat:
        ...

    def deps(self, project: model.Project) -> list[PackageSpec]:
        deps = []
        for v in project.extern.values():
            deps += self.packageName(v)
        return deps

    def buildDeps(self) -> list[PackageSpec]:
        return []

    def packageName(self, extern : model.Extern)-> list[PackageSpec]:
        # Ignore cutekit packages
        if extern.git:
            return []

        if extern.id in self.packages:
            return self.packages[extern.id]

        raise RuntimeError(f"No package mapping for {extern.id} on {self.family} {self.version}")

class Debian(Distro):
    def packageFormat(self) -> PackageFormat:
        return Deb()

    def buildDeps(self) -> list[PackageSpec]:
        return [
            PackageSpec(buildDep="build-essential"),
            PackageSpec(buildDep="git"),
            PackageSpec(buildDep="ninja-build"),
            PackageSpec(buildDep="jq"),
            PackageSpec(buildDep="pkg-config"),
            PackageSpec(buildDep="curl"),
            PackageSpec(buildDep="ca-certificates"),
        ]

    def packageName(self, extern : model.Extern) -> list[PackageSpec]:
        match extern.id:
            case "sdl3":
                return [PackageSpec("libsdl3, libsdl3-dev")]
            case "uring":
                return [PackageSpec("liburing, liburing-dev")]
            case "seccomp":
                return [PackageSpec("libseccomp, libseccomp-dev")]
        return super().packageName(extern)

class Ubuntu(Debian):
    pass


DISTROS = {
    ("debian", "testing"): Debian("debian", "testing"),
    ("Debian", "trixie"): Debian("Debian", "trixie"),
    ("debian", "bookworm"): Debian("debian", "bookworm"),

    ("ubuntu", "resolute"): Ubuntu("ubuntu", "resolute"), # 26.04
    ("ubuntu", "noble"): Ubuntu("ubuntu", "noble"), # 24.04
    ("ubuntu", "jammy"): Ubuntu("ubuntu", "jammy"), # 22.04
}

def curentDistro() -> Distro:
    if os.path.exists("/etc/os-release"):
        info = {}
        with open("/etc/os-release", "r") as f:
            for line in f:
                if "=" in line:
                    key, value = line.strip().split("=", 1)
                    info[key] = value.strip('"')

        id = info.get("ID")
        version = info.get("VERSION_ID")

        if id and version and (id, version) in DISTROS:
            return DISTROS[(id, version)]

    raise RuntimeError("Unsupported distro")

class PackageArgs(model.TargetArgs):
    component: str = cli.operand("component", "Component to package", default="__main__")
    layout: str = cli.arg(None, "layout", "Installation layout")
    sysroot: str = cli.arg(None, "sysroot", "System root directory", "/")

    distro : str = cli.arg(None, "distro", "Target distribution (e.g. debian-bookworm)", "auto")
    maintainer: str = cli.arg(None, "maintainer", "Package maintainer")
    out : str = cli.arg(None, "out", "Output package path")

def package(args: PackageArgs):
    args.sysroot = os.path.abspath(args.sysroot or "/")
    registry = model.Registry.use(args)
    target = model.Target.use(args)
    scope = builder.TargetScope(registry, target)

    registry = model.Registry.use(args)
    toInstall = registry.ensure(args.component, model.Component, includeProvides=True)
    required = toInstall.resolved[target.id].required
    products = builder.build(scope, [toInstall] + required)

    dest = Path(args.sysroot) / Path(args.prefix).relative_to("/")
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
