import os
import logging
import dataclasses as dt


from enum import Enum
from typing import Any, Generator, Optional, Type, cast
from pathlib import Path
from dataclasses_json import DataClassJsonMixin

from cutekit import const, shell

from . import cli, jexpr, compat, utils, vt100

_logger = logging.getLogger(__name__)

Props = dict[str, Any]


class Kind(Enum):
    UNKNOWN = "unknown"
    PROJECT = "project"
    TARGET = "target"
    LIB = "lib"
    EXE = "exe"


# --- Manifest --------------------------------------------------------------- #


@dt.dataclass
class Manifest(DataClassJsonMixin):
    id: str
    type: Kind = dt.field(default=Kind.UNKNOWN)
    path: str = dt.field(default="")
    SUFFIXES = [".json", ".toml"]
    SUFFIXES_GLOBS = ["*.json", "*.toml"]

    @staticmethod
    def parse(path: Path, data: dict[str, Any]) -> "Manifest":
        """
        Parse a manifest from a given path and data
        """
        compat.ensureSupportedManifest(data, path)
        kind = Kind(data["type"])
        del data["$schema"]
        obj = KINDS[kind].from_dict(data)
        obj.path = str(path)
        return obj

    @staticmethod
    def tryLoad(path: Path) -> Optional["Manifest"]:
        """
        Try to load a manifest from a given path
        """
        for suffix in Manifest.SUFFIXES:
            pathWithSuffix = path.with_suffix(suffix)
            if pathWithSuffix.exists():
                _logger.debug(f"Loading manifest from '{pathWithSuffix}'")
                data = jexpr.include(pathWithSuffix)
                if not isinstance(data, dict):
                    raise RuntimeError(
                        f"Manifest '{pathWithSuffix}' should be a dictionary"
                    )
                return Manifest.parse(pathWithSuffix, data)
        return None

    @staticmethod
    def load(path: Path) -> "Manifest":
        """
        Load a manifest from a given path
        """
        manifest = Manifest.tryLoad(path)
        if manifest is None:
            raise RuntimeError(f"Could not find manifest at '{path}'")
        return manifest

    def dirname(self) -> str:
        """
        Return the directory of the manifest
        """
        return os.path.relpath(os.path.dirname(self.path), Path.cwd())

    def subpath(self, path) -> Path:
        """
        Return a subpath of the manifest

        Example:
            manifest.subpath("src") -> Path(manifest.dirname() + "/src")
        """
        return Path(self.dirname()) / path

    def ensureType(self, t: Type[utils.T]) -> utils.T:
        """
        Ensure that the manifest is of a given type
        """
        if not isinstance(self, t):
            raise RuntimeError(
                f"{self.path} should be a {type.__name__} manifest but is a {self.__class__.__name__} manifest"
            )
        return cast(utils.T, self)


# --- Project ---------------------------------------------------------------- #

_project: Optional["Project"] = None


@dt.dataclass
class Extern:
    id: str = dt.field(default="")
    description: str = dt.field(default="(No description)")

    # The following properties are for package comming from git
    git: str = dt.field(default="")
    tag: str = dt.field(default="")
    shallow: bool = dt.field(default=True)
    depth: int = dt.field(default=1)

    # Name under which the extern is installed
    # might be the package name on linux or MacOS
    names: list[str] = dt.field(default_factory=list)

    def _fetchLibrary(self) -> list["Manifest"]:
        """
        Locate a library on the host system and create a virtual
        manifest for it
        """
        c = Component(f"{self.id}-host", Kind.LIB)
        c.description = f"Host version of {self.id}"
        c.path = "src/_virtual"
        c.enableIf = {"host": [True]}
        c.provides = [self.id]

        def pkgExists(name: str) -> bool:
            try:
                shell.popen("pkg-config", "--exists", name)
                return True
            except shell.ShellException:
                return False

        for name in self.names:
            if not pkgExists(name):
                continue

            _logger.info(f"Found {name} on the host system")

            cflags = shell.popen("pkg-config", "--cflags", self.id).strip()
            ldflags = shell.popen("pkg-config", "--libs", self.id).strip()

            c.tools["cc"] = Tool(args=cflags.split())
            c.tools["cxx"] = Tool(args=cflags.split())
            c.tools["ld"] = Tool(args=ldflags.split())

            return [c]

        return []

    def _fetchGit(self) -> list[Manifest]:
        """
        Fetch an extern from a git repository
        """
        path = os.path.join(const.EXTERN_DIR, self.id)

        if os.path.exists(path):
            _logger.info(f"Extern {self.id} already exists at {path}")
            project = Project.at(Path(path))
            if not project:
                _logger.warn("Extern project does not have a project")
                return []
            return [project] + project.fetchExterns()

        _logger.info(f"Installing {self.id}-{self.tag} from {self.git}...")
        cmd = [
            "git",
            "clone",
            "--quiet",
            "--branch",
            self.tag,
            self.git,
            path,
        ]

        if self.shallow:
            cmd += ["--depth", str(self.depth)]

        shell.exec(*cmd, quiet=True)
        project = Project.at(Path(path))
        if project is None:
            # Maybe it's a single manifest project.
            # It's useful for externs that are simple self-contained libraries
            # that don't need a full project structure
            manifest = Manifest.tryLoad(Path(path) / "manifest")
            if manifest is not None:
                return [manifest]
            _logger.warn("Extern project does not have a project or manifest")
            return []
        return [cast(Manifest, project)] + project.fetchExterns()

    def fetch(self) -> list[Manifest]:
        if self.git:
            return self._fetchGit()
        else:
            return self._fetchLibrary()


@dt.dataclass
class Project(Manifest):
    description: str = dt.field(default="(No description)")
    extern: dict[str, Extern] = dt.field(default_factory=dict)

    @property
    def externDirs(self) -> list[str]:
        res = map(lambda e: os.path.join(const.EXTERN_DIR, e), self.extern.keys())
        return list(res)

    @staticmethod
    def topmost() -> Optional["Project"]:
        cwd = Path.cwd()
        topmost: Optional["Project"] = None
        while str(cwd) != cwd.root:
            projectManifest = Manifest.tryLoad(cwd / "project")
            if projectManifest is not None:
                topmost = projectManifest.ensureType(Project)
            cwd = cwd.parent
        return topmost

    @staticmethod
    def ensure() -> "Project":
        """
        Ensure that a project exists in the current directory or any parent directory
        and chdir to the root of the project.
        """
        project = Project.topmost()
        if project is None:
            raise RuntimeError(
                "No project found in this directory or any parent directory"
            )
        os.chdir(project.dirname())
        return project

    @staticmethod
    def at(path: Path) -> Optional["Project"]:
        projectManifest = Manifest.tryLoad(path / "project")
        if projectManifest is None:
            return None
        return projectManifest.ensureType(Project)

    def fetchExterns(self) -> list[Manifest]:
        """
        Fetch all externs for the project
        """

        res = []
        for extSpec, ext in self.extern.items():
            ext.id = extSpec
            res.extend(ext.fetch())

        return utils.uniq(res, lambda x: x.id)

    @staticmethod
    def use() -> "Project":
        global _project
        if _project is None:
            _project = Project.ensure()
        return _project


@cli.command("m", "model", "Manage the model")
def _():
    pass


@cli.command("i", "model/install", "Install required external packages")
def _():
    project = Project.use()
    project.fetchExterns()


class ModelInitArgs:
    repo: str = cli.arg(
        None,
        "repo",
        "The repository to fetch templates from",
        default=const.DEFAULT_REPO_TEMPLATES,
    )
    list: bool = cli.arg("l", "list", "List available templates")
    template: str = cli.operand("template", "The template to use")
    name: str = cli.operand("name", "The name of the project")


@cli.command("I", "model/init", "Initialize a new project")
def _(args: ModelInitArgs):
    import requests

    _logger.info("Fetching registry...")

    r = requests.get(
        f"https://raw.githubusercontent.com/{args.repo}/main/registry.json"
    )

    if r.status_code != 200:
        _logger.error("Failed to fetch registry")
        exit(1)

    registry = r.json()

    if args.list:
        print(
            "\n".join(f"* {entry['id']} - {entry['description']}" for entry in registry)
        )
        return

    if not args.template:
        raise RuntimeError("Template not specified")

    def template_match(t: Any) -> bool:
        if not isinstance(t, dict):
            return False
        return t["id"] == args.template

    if not any(filter(template_match, registry)):
        raise LookupError(f"Couldn't find a template named {args.template}")

    if not args.name:
        _logger.info(f"No name was provided, defaulting to {args.template}")
        args.name = args.template

    if os.path.exists(args.name):
        raise RuntimeError(f"Directory {args.name} already exists")

    print(f"Creating project {args.name} from template {args.template}...")
    shell.cloneDir(f"https://github.com/{args.repo}", args.template, args.name)
    print(f"Project {args.name} created\n")

    print("We suggest that you begin by typing:")
    print(f"  {vt100.GREEN}cd {args.name}{vt100.RESET}")
    print(
        f"  {vt100.GREEN}cutekit install{vt100.BRIGHT_BLACK} # Install external packages{vt100.RESET}"
    )
    print(
        f"  {vt100.GREEN}cutekit build{vt100.BRIGHT_BLACK}  # Build the project{vt100.RESET}"
    )


# --- Target ----------------------------------------------------------------- #


@dt.dataclass
class Tool(DataClassJsonMixin):
    cmd: str = dt.field(default="")
    args: list[str] = dt.field(default_factory=list)
    files: list[str] = dt.field(default_factory=list)
    rule: Optional[str] = None


Tools = dict[str, Tool]

DEFAULT_TOOLS: Tools = {
    "cp": Tool("cp"),
}


class RegistryArgs:
    props: dict[str, jexpr.Jexpr] = cli.arg(None, "props", "Set a property")
    mixins: list[str] = cli.arg(None, "mixins", "Apply mixins")


class TargetArgs(RegistryArgs):
    target: str = cli.arg(
        None, "target", "The target to use", default="host-" + shell.uname().machine
    )


@dt.dataclass
class Target(Manifest):
    props: Props = dt.field(default_factory=dict)
    tools: Tools = dt.field(default_factory=dict)
    routing: dict[str, str] = dt.field(default_factory=dict)

    _hashid: Optional[str] = None

    @property
    def hashid(self) -> str:
        if self._hashid is None:
            self._hashid = utils.hash(
                (self.props, [v.to_dict() for k, v in self.tools.items()])
            )
        return self._hashid

    @property
    def builddir(self) -> str:
        postfix = f"-{self.hashid[:8]}"
        if self.props.get("host"):
            postfix += f"-{str(const.HOSTID)[:8]}"
        return os.path.join(const.BUILD_DIR, f"{self.id}{postfix}")

    @staticmethod
    def use(args: TargetArgs) -> "Target":
        registry = Registry.use(args)
        return registry.ensure(args.target, Target)

    def route(self, componentSpec: str):
        """
        Route a component spec to a target specific component spec
        """
        return (
            self.routing[componentSpec]
            if componentSpec in self.routing
            else componentSpec
        )


# --- Component -------------------------------------------------------------- #


@dt.dataclass
class Resolved:
    reason: Optional[str] = None
    required: list[str] = dt.field(default_factory=list)
    injected: list[str] = dt.field(default_factory=list)

    @property
    def enabled(self) -> bool:
        return self.reason is None


@dt.dataclass
class Component(Manifest):
    description: str = dt.field(default="(No description)")
    props: Props = dt.field(default_factory=dict)
    tools: Tools = dt.field(default_factory=dict)
    enableIf: dict[str, list[Any]] = dt.field(default_factory=dict)
    requires: list[str] = dt.field(default_factory=list)
    provides: list[str] = dt.field(default_factory=list)
    subdirs: list[str] = dt.field(default_factory=list)
    injects: list[str] = dt.field(default_factory=list)
    resolved: dict[str, Resolved] = dt.field(default_factory=dict)

    def isEnabled(self, target: Target) -> tuple[bool, str]:
        for k, v in self.enableIf.items():
            if k not in target.props:
                _logger.info(f"Component {self.id} disabled by missing {k} in target")
                return False, f"Missing props '{k}' in target"

            if target.props[k] not in v:
                vStrs = [f"'{str(x)}'" for x in v]
                _logger.info(
                    f"Component {self.id} disabled by {k}={target.props[k]} not in {v}"
                )
                return (
                    False,
                    f"Props missmatch for '{k}': Got '{target.props[k]}' but expected {', '.join(vStrs)}",
                )

        return True, ""


KINDS: dict[Kind, Type[Manifest]] = {
    Kind.PROJECT: Project,
    Kind.TARGET: Target,
    Kind.LIB: Component,
    Kind.EXE: Component,
}

# --- Dependency resolution -------------------------------------------------- #


@dt.dataclass
class Resolver:
    _registry: "Registry"
    _target: Target
    _mappings: dict[str, list[Component]] = dt.field(default_factory=dict)
    _cache: dict[str, Resolved] = dt.field(default_factory=dict)
    _baked = False

    def _bake(self):
        """
        Bake the resolver by building a mapping of all
        components that provide a given spec.
        """

        if self._baked:
            return

        for c in self._registry.iter(Component):
            for p in c.provides + [c.id]:
                if p not in self._mappings and [0]:
                    self._mappings[p] = []
                self._mappings[p].append(c)

        # Overide with target routing since it has priority
        # over component provides and id
        for k, v in self._target.routing.items():
            component = self._registry.lookup(v, Component)
            self._mappings[k] = [component] if component else []

        self._baked = True

    def _provider(self, spec: str) -> tuple[Optional[str], str]:
        """
        Returns the provider for a given spec.
        """
        result = self._mappings.get(spec, [])

        if len(result) == 1:
            enabled, reason = result[0].isEnabled(self._target)
            if not enabled:
                return (None, reason)

        def checkIsEnabled(c: Component) -> bool:
            enabled, reason = c.isEnabled(self._target)
            if not enabled:
                _logger.info(f"Component {c.id} cannot provide '{spec}': {reason}")
            return enabled

        result = list(filter(checkIsEnabled, result))

        if result == []:
            return (None, f"No provider for '{spec}'")

        if len(result) > 1:
            ids = list(map(lambda x: x.id, result))
            return (None, f"Multiple providers for '{spec}': {','.join(ids)}")

        return (result[0].id, "")

    def resolve(self, what: str, stack: list[str] = []) -> Resolved:
        """
        Resolve a given spec to a list of components.
        """
        self._bake()

        if what in self._cache:
            return self._cache[what]

        keep, unresolvedReason = self._provider(what)

        if not keep:
            _logger.error(f"Dependency '{what}' not found: {unresolvedReason}")
            self._cache[what] = Resolved(reason=unresolvedReason)
            return self._cache[what]

        if keep in self._cache:
            return self._cache[keep]

        if keep in stack:
            raise RuntimeError(
                f"Dependency loop while resolving '{what}': {stack} -> {keep}"
            )

        stack.append(keep)

        component = self._registry.lookup(keep, Component)
        if not component:
            return Resolved(f"No provider for '{keep}'")

        result: list[str] = []

        for req in component.requires:
            reqResolved = self.resolve(req, stack)
            if reqResolved.reason:
                stack.pop()

                self._cache[keep] = Resolved(reason=reqResolved.reason)
                return self._cache[keep]

            result.extend(reqResolved.required)

        stack.pop()
        result.insert(0, keep)
        self._cache[keep] = Resolved(required=utils.uniqPreserveOrder(result))
        return self._cache[keep]


# --- Registry --------------------------------------------------------------- #

_registry: Optional["Registry"] = None


@dt.dataclass
class Registry(DataClassJsonMixin):
    project: Project
    manifests: dict[str, Manifest] = dt.field(default_factory=dict)

    def _append(self, m: Optional[Manifest]) -> Optional[Manifest]:
        """
        Append a manifest to the model
        """
        if m is None:
            return m

        if m.id in self.manifests:
            raise RuntimeError(
                f"Duplicated manifest '{m.id}' at '{m.path}' already loaded from '{self.manifests[m.id].path}'"
            )

        self.manifests[m.id] = m
        return m

    def iter(self, type: Type[utils.T]) -> Generator[utils.T, None, None]:
        """
        Iterate over all manifests of a given type
        """

        for m in self.manifests.values():
            if isinstance(m, type):
                yield m

    def iterEnabled(self, target: Target) -> Generator[Component, None, None]:
        for c in self.iter(Component):
            resolve = c.resolved[target.id]
            if resolve.enabled:
                yield c

    def lookup(
        self, name: str, type: Type[utils.T], includeProvides: bool = False
    ) -> Optional[utils.T]:
        """
        Lookup a manifest of a given type by name
        """

        if name in self.manifests:
            m = self.manifests[name]
            if isinstance(m, type):
                return m

        if includeProvides and type is Component:
            for m in self.iter(Component):
                if name in m.provides:
                    return m  # type: ignore

        return None

    def ensure(self, name: str, type: Type[utils.T]) -> utils.T:
        """
        Ensure that a manifest of a given type exists
        and return it.
        """

        m = self.lookup(name, type)
        if not m:
            raise RuntimeError(f"Could not find {type.__name__} '{name}'")
        return m

    @staticmethod
    def use(args: RegistryArgs) -> "Registry":
        global _registry

        if _registry is not None:
            return _registry

        project = Project.use()
        _registry = Registry.load(project, args.mixins, args.props)
        return _registry

    @staticmethod
    def _loadExterns(r: "Registry", p: Project):
        """
        Load all externs for the project
        """
        externs = p.fetchExterns()
        for extern in externs:
            r._append(extern)

    @staticmethod
    def _loadManifests(r: "Registry"):
        """
        Load all manifests for each project in the registry
        """

        for project in list(r.iter(Project)):
            targetDir = os.path.join(project.dirname(), const.TARGETS_DIR)
            targetFiles = shell.find(targetDir, Manifest.SUFFIXES_GLOBS)

            for targetFile in targetFiles:
                r._append(Manifest.load(Path(targetFile)).ensureType(Target))

            componentFiles = shell.find(
                os.path.join(project.dirname(), const.SRC_DIR),
                ["manifest" + s for s in Manifest.SUFFIXES],
            )

            rootComponent = Manifest.tryLoad(Path(project.dirname()) / "manifest")
            if rootComponent is not None:
                r._append(rootComponent)

            for componentFile in componentFiles:
                r._append(Manifest.load(Path(componentFile)).ensureType(Component))

    @staticmethod
    def _loadDependencies(r: "Registry", mixins: list[str], props: Props):
        """
        Resolve all dependencies for all targets
        """

        for target in r.iter(Target):
            target.props |= props

            # Resolve all components
            resolver = Resolver(r, target)
            for c in r.iter(Component):
                resolved = resolver.resolve(c.id)
                if resolved.reason:
                    _logger.info(f"Component '{c.id}' disabled: {resolved.reason}")
                c.resolved[target.id] = resolved

            # Apply injects
            for c in r.iter(Component):
                if c.resolved[target.id].enabled:
                    for inject in c.injects:
                        victim = r.lookup(inject, Component, includeProvides=True)
                        if not victim:
                            _logger.info(
                                f"Could not find component to inject '{inject}' with '{c.id}'"
                            )
                        else:
                            victim.resolved[target.id].injected.append(c.id)
                            victim.resolved[
                                target.id
                            ].required = utils.uniqPreserveOrder(
                                c.resolved[target.id].required
                                + victim.resolved[target.id].required
                            )

            # Resolve tooling
            tools: Tools = target.tools

            # Merge in default tools
            for k, v in DEFAULT_TOOLS.items():
                if k not in tools:
                    tools[k] = dt.replace(v)

            from . import mixins as mxs

            for mix in mixins:
                mixin = mxs.byId(mix)
                tools = mixin(target, tools)

            # Apply tooling from components
            for c in r.iter(Component):
                if c.resolved[target.id].enabled:
                    for k, v in c.tools.items():
                        tools[k].args += v.args

    @staticmethod
    def load(project: Project, mixins: list[str], props: Props) -> "Registry":
        """
        Load the model for a given project, applying mixins and props
        """
        _logger.info(f"Loading model for project '{project.id}'")

        r = Registry(project)
        r._append(project)

        Registry._loadExterns(r, project)
        Registry._loadManifests(r)
        Registry._loadDependencies(r, mixins, props)

        return r


@cli.command("l", "model/list", "List all components and targets")
def _(args: TargetArgs):
    registry = Registry.use(args)
    components = list(registry.iter(Component))
    targets = list(registry.iter(Target))

    vt100.title("Components")
    if len(components) == 0:
        print(vt100.p("(No components available)"))
    else:
        print(vt100.p(", ".join(map(lambda m: m.id, components))))
    print()

    vt100.title("Targets")

    if len(targets) == 0:
        print(vt100.p("(No targets available)"))
    else:
        print(vt100.p(", ".join(map(lambda m: m.id, targets))))
    print()


@cli.command("d", "model/dump", "Dump the model")
def _(args: TargetArgs):
    registry = Registry.use(args)
    print("[")
    for m in registry.manifests.values():
        print(m.to_json(indent=2), end="")
        print(",")
    print("]")
