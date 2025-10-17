import os
import json
import logging
import dataclasses as dt


from enum import Enum
from typing import Any, Generator, Optional, Type, cast
from pathlib import Path
from dataclasses_json import DataClassJsonMixin

from cutekit import const, shell

from . import cli, jexpr, utils, vt100

_logger = logging.getLogger(__name__)

Props = dict[str, Any]


class Kind(Enum):
    """
    Enum representing the different kinds of manifests.
    """

    UNKNOWN = "unknown"
    PROJECT = "project"
    TARGET = "target"
    LIB = "lib"
    EXE = "exe"


# MARK: Manifest ---------------------------------------------------------------

SUPPORTED_MANIFEST = [
    "https://schemas.cute.engineering/stable/cutekit.manifest.component.v1",
    "https://schemas.cute.engineering/stable/cutekit.manifest.project.v1",
    "https://schemas.cute.engineering/stable/cutekit.manifest.target.v1",
]


def ensureSupportedManifest(manifest: Any, path: Path):
    """
    Ensure that a manifest is supported.

    Args:
        manifest: The manifest to check.

    Raises:
        RuntimeError: If the manifest is not supported.
    """

    if "$schema" not in manifest:
        raise RuntimeError(f"Missing $schema in {path}")

    if manifest["$schema"] not in SUPPORTED_MANIFEST:
        raise RuntimeError(
            f"Unsupported manifest schema {manifest['$schema']} in {path}"
        )


@dt.dataclass
class Manifest(DataClassJsonMixin):
    """
    Base class for all manifests.
    """

    id: str
    """Unique identifier of the manifest."""
    type: Kind = dt.field(default=Kind.UNKNOWN)
    """Type of the manifest."""
    path: str = dt.field(default="")
    """Path to the manifest file."""

    SUFFIXES = [".json", ".toml"]
    """Supported file extensions for manifest files."""
    SUFFIXES_GLOBS = ["*.json", "*.toml"]
    """Glob patterns for finding manifest files."""

    @staticmethod
    def parse(path: Path, data: dict[str, Any]) -> "Manifest":
        """
        Parse a manifest from a given path and data.

        Args:
            path: Path to the manifest file.
            data: Dictionary containing the manifest data.

        Returns:
            The parsed Manifest object.
        """
        ensureSupportedManifest(data, path)
        kind = Kind(data["type"])
        del data["$schema"]
        obj = KINDS[kind].from_dict(data)
        obj.path = str(path)
        return obj

    @staticmethod
    def tryLoad(path: Path) -> Optional["Manifest"]:
        """
        Try to load a manifest from a given path.

        Args:
            path: Path to the directory containing the manifest file.

        Returns:
            The loaded Manifest object, or None if no manifest file was found.
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
        Load a manifest from a given path.

        Args:
            path: Path to the directory containing the manifest file.

        Returns:
            The loaded Manifest object.

        Raises:
            RuntimeError: If no manifest file was found.
        """
        manifest = Manifest.tryLoad(path)
        if manifest is None:
            raise RuntimeError(f"Could not find manifest at '{path}'")
        return manifest

    def dirname(self) -> str:
        """
        Return the directory of the manifest.

        Returns:
            The directory of the manifest.
        """
        return os.path.relpath(os.path.dirname(self.path), Path.cwd())

    def subpath(self, path) -> Path:
        """
        Return a subpath of the manifest.

        Example:
            manifest.subpath("src") -> Path(manifest.dirname() + "/src")

        Args:
            path: The subpath to append.

        Returns:
            The complete subpath.
        """
        return Path(self.dirname()) / path

    def ensureType(self, t: Type[utils.T]) -> utils.T:
        """
        Ensure that the manifest is of a given type.

        Args:
            t: The expected type of the manifest.

        Returns:
            The manifest object cast to the expected type.

        Raises:
            RuntimeError: If the manifest is not of the expected type.
        """
        if not isinstance(self, t):
            raise RuntimeError(
                f"{self.path} should be a {type.__name__} manifest but is a {self.__class__.__name__} manifest"
            )
        return cast(utils.T, self)


# MARK: Lockfile ---------------------------------------------------------------


@dt.dataclass
class LockEntry(DataClassJsonMixin):
    git: str
    ref: str
    commit: str


@dt.dataclass
class ProjectLock:
    _data: dict[str, LockEntry] = dt.field(default_factory=dict)
    _loaded: bool = dt.field(default=False)
    _dir: Path = dt.field(default=Path(""))

    def __init__(self, dir: Path):
        self._dir = dir

    def _file(self) -> Path:
        root = Path(os.path.dirname(self._dir))
        return root / "project.lock"

    def load(self):
        if self._loaded:
            return
        f = self._file()
        if f.exists():
            raw = jexpr.include(f)
            if isinstance(raw, dict):
                for k, v in raw.items():
                    try:
                        self._data[k] = LockEntry.from_dict(v)
                    except Exception:
                        _logger.warning(f"Invalid lock entry for '{k}' in {f}")
        self._loaded = True

    def save(self):
        self.load()
        f = self._file()
        payload = {k: v.to_dict() for k, v in sorted(self._data.items())}
        f.write_text(json.dumps(payload, indent=2) + "\n")

    def get(self, extern_id: str) -> Optional[LockEntry]:
        self.load()
        return self._data.get(extern_id)

    def set(self, extern_id: str, entry: LockEntry):
        self.load()
        self._data[extern_id] = entry
        self.save()


# MARK: Project ----------------------------------------------------------------

_project: Optional["Project"] = None


@dt.dataclass
class Extern(DataClassJsonMixin):
    """
    Represents an external dependency of a project.
    """

    id: str = dt.field(default="")
    """Unique identifier of the external dependency."""
    description: str = dt.field(default="(No description)")
    """Description of the external dependency."""

    # The following properties are for package comming from git
    git: str = dt.field(default="")
    """Git repository URL."""
    tag: str = dt.field(default="")
    """Git tag or branch to checkout."""
    shallow: bool = dt.field(default=True)
    """Whether to perform a shallow clone."""
    depth: int = dt.field(default=1)
    """Depth of the shallow clone."""

    # Name under which the extern is installed
    # might be the package name on linux or MacOS
    names: list[str] = dt.field(default_factory=list)
    """Names under which the external dependency might be installed."""

    def _fetchLibrary(self) -> list["Manifest"]:
        """
        Locate a library on the host system and create a virtual
        manifest for it.

        Returns:
            A list containing the virtual manifest if the library is found,
            otherwise an empty list.
        """
        c = Component(f"{self.id}-host", Kind.LIB)
        c.description = f"Host version of {self.id}"
        c.path = "src/_virtual"
        c.enableIf = {
            "host": [True],
            "sys": [shell.uname().sysname.lower()],
            "arch": [shell.uname().machine],
        }
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

            cflags = shell.popen("pkg-config", "--cflags", name).strip()
            ldflags = shell.popen("pkg-config", "--libs", name).strip()

            c.tools["cc"] = Tool(args=cflags.split())
            c.tools["cxx"] = Tool(args=cflags.split())
            c.tools["ld"] = Tool(args=ldflags.split())

            return [c]

        return []

    # Lock-aware git fetch
    def fetch(
        self, project: "Project", dev: bool = False, updateLock: bool = False
    ) -> list[Manifest]:
        if self.git:
            return self._fetchGit(project, dev=dev, updateLock=updateLock)
        else:
            return self._fetchLibrary()

    def _git(self, *args: str, cwd: Optional[Path] = None) -> str:
        return shell.popen("git", *args, cwd=cwd).strip()

    def _fetchGit(
        self, project: "Project", dev: bool, updateLock: bool
    ) -> list[Manifest]:
        """
        Fetch an extern from a git repository, honoring project.lock and --dev.
        """
        path = os.path.join(const.EXTERN_DIR, self.id)
        globalPath = os.path.join(const.GLOBAL_EXTERN_DIR, self.id)

        if os.path.exists(globalPath):
            print(f"Using global extern {self.id} from {globalPath}")
            path = globalPath

        # Decide ref and whether we're locking
        ref_for_latest = "main" if dev else (self.tag or "main")
        lock = project.lock()
        entry = lock.get(self.id)

        # Clone if missing
        if not os.path.exists(path):
            print(f"Installing {self.id} from {self.git}...")
            cmd = ["git", "clone", "--quiet", "--no-checkout", self.git, path]
            if self.shallow:
                cmd += ["--depth", str(self.depth)]
            shell.exec(*cmd, quiet=True)

        # Fetch updates
        try:
            shell.exec("git", "fetch", "--quiet", "origin", cwd=path)
        except shell.ShellException:
            pass

        def checkout_commit(commit: str):
            shell.exec("git", "checkout", "--quiet", "--detach", commit, cwd=path)

        def latest_commit_for(ref: str) -> str:
            try:
                return self._git("rev-parse", f"origin/{ref}", cwd=Path(path))
            except shell.ShellException:
                return self._git("rev-parse", ref, cwd=Path(path))

        if dev:
            commit = latest_commit_for(ref_for_latest)
            checkout_commit(commit)
            # no lock writes in dev mode
        else:
            if updateLock:
                latest = latest_commit_for(ref_for_latest)
                checkout_commit(latest)
                lock.set(
                    self.id, LockEntry(git=self.git, ref=ref_for_latest, commit=latest)
                )
                print(f"Locked {self.id} @ {ref_for_latest} -> {latest[:12]}")
            else:
                if entry:
                    checkout_commit(entry.commit)
                else:
                    latest = latest_commit_for(ref_for_latest)
                    checkout_commit(latest)
                    lock.set(
                        self.id,
                        LockEntry(git=self.git, ref=ref_for_latest, commit=latest),
                    )
                    print(f"Locked {self.id} @ {ref_for_latest} -> {latest[:12]}")

        # Load manifests from the extern
        projectObj = Project.at(Path(path))
        if projectObj is None:
            manifest = Manifest.tryLoad(Path(path) / "manifest")
            if manifest is not None:
                return [manifest]
            _logger.warn("Extern project does not have a project or manifest")
            return []
        return [cast(Manifest, projectObj)] + projectObj.fetchExterns(
            dev=dev, updateLock=updateLock
        )


@dt.dataclass
class Project(Manifest):
    """
    Represents a CuteKit project.
    """

    description: str = dt.field(default="(No description)")
    version: str = dt.field(default="0.0.1")
    """Description of the project."""
    extern: dict[str, Extern] = dt.field(default_factory=dict)
    """External dependencies of the project."""

    @property
    def externDirs(self) -> list[str]:
        """
        Returns a list of directories where external dependencies are located.

        Returns:
            A list of directories.
        """
        res = map(lambda e: os.path.join(const.EXTERN_DIR, e), self.extern.keys())
        return list(res)

    def lock(self) -> ProjectLock:
        return ProjectLock(Path(self.path))

    def _externCheckoutDir(self, ext_id: str) -> str:
        local = os.path.join(const.EXTERN_DIR, ext_id)
        global_path = os.path.join(const.GLOBAL_EXTERN_DIR, ext_id)
        return global_path if os.path.exists(global_path) else local

    def verifyExterns(self) -> int:
        """
        Verify extern checkouts match project.lock.
        Returns number of errors found.
        """
        lock = self.lock()
        lock.load()

        externs: dict[str, Extern] = {}
        for extId, ext in self.extern.items():
            e = dt.replace(ext)
            e.id = extId
            externs[extId] = e

        errors = 0

        for extId, ext in externs.items():
            entry = lock.get(extId)
            path = self._externCheckoutDir(extId)

            def err(msg: str):
                nonlocal errors
                errors += 1
                print(f"[FAIL] {extId}: {msg}")

            def warn(msg: str):
                print(f"[WARN] {extId}: {msg}")

            if entry is None:
                err("no lock entry")
                continue

            if not os.path.exists(path):
                err(f"checkout missing at {path}")
                continue

            ref = ext.tag or "main"
            if entry.git != ext.git or entry.ref != ref:
                warn(
                    f"lock git/ref differs from manifest "
                    f"(lock: {entry.git}@{entry.ref}, manifest: {ext.git}@{ref})"
                )

            try:
                head = shell.popen("git", "rev-parse", "HEAD", cwd=Path(path)).strip()
            except shell.ShellException as ex:
                err(f"cannot read HEAD: {ex}")
                continue

            if head != entry.commit:
                err(f"HEAD {head[:12]} != locked {entry.commit[:12]}")
                continue

            print(f"[OK]   {extId}: {head[:12]} matches lock")

        lockedIds = set(lock._data.keys())
        declaredIds = set(externs.keys())
        extras = sorted(lockedIds - declaredIds)
        for x in extras:
            print(f"[WARN] lock entry '{x}' not referenced by project externs")

        return errors

    @staticmethod
    def topmost() -> Optional["Project"]:
        """
        Find the topmost project in the current directory hierarchy.

        Returns:
            The topmost Project object, or None if no project was found.
        """
        cwd = Path.cwd()
        topmost: Optional["Project"] = None
        while str(cwd) != cwd.anchor:
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

        Returns:
            The Project object.

        Raises:
            RuntimeError: If no project was found.
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
        """
        Try to load a project from a given path.

        Args:
            path: Path to the directory containing the project manifest.

        Returns:
            The Project object, or None if no project was found.
        """
        projectManifest = Manifest.tryLoad(path / "project")
        if projectManifest is None:
            return None
        return projectManifest.ensureType(Project)

    def fetchExterns(
        self, dev: bool = False, updateLock: bool = False
    ) -> list[Manifest]:
        """
        Fetch all externs for the project.

        Returns:
            A list of manifests representing the fetched external dependencies.
        """

        res = []
        for extSpec, ext in self.extern.items():
            ext.id = extSpec
            res.extend(ext.fetch(self, dev=dev, updateLock=updateLock))

        return utils.uniq(res, lambda x: x.id)

    @staticmethod
    def use() -> "Project":
        """
        Get the currently active project.

        Returns:
            The currently active Project object.
        """
        global _project
        if _project is None:
            _project = Project.ensure()
        return _project


@cli.command("model", "Manage the model")
def _():
    """
    Manage the CuteKit model.
    """
    pass


@cli.command("model/install", "Install required external packages")
def _(args: "RegistryArgs"):
    """
    Install required external packages for the project.
    """
    project = Project.use()
    project.fetchExterns(dev=args.dev)


# MARK: Target -----------------------------------------------------------------


@dt.dataclass
class Tool(DataClassJsonMixin):
    """
    Represents a build tool.
    """

    cmd: str = dt.field(default="")
    """Command to execute."""
    args: list[str] = dt.field(default_factory=list)
    """Arguments to pass to the command."""
    files: list[str] = dt.field(default_factory=list)
    """List of files associated with the tool."""
    rule: Optional[str] = None
    """Build rule associated with the tool."""


Tools = dict[str, Tool]
"""Type alias for a dictionary of tools."""

DEFAULT_TOOLS: Tools = {
    "cp": Tool("cp"),
    "ld-shared": Tool(shell.latest("clang++")),
    "cxx-scan": Tool(shell.latest("clang-scan-deps")),
    "cxx-collect": Tool("jq"),
    "cxx-modmap": Tool("ck --safemode tools cxx-modmap"),
    "cxx-dyndep": Tool("ck --safemode tools cxx-dyndep"),
}
"""Default tools available in all projects."""


class RegistryArgs:
    """
    Arguments for the Registry class.
    """

    props: dict[str, str] = cli.arg(None, "props", "Set a property")
    """Properties to set on the registry."""
    mixins: list[str] = cli.arg(None, "mixins", "Apply mixins")
    """Mixins to apply to the registry."""
    release: bool = cli.arg(None, "release", "Build in release mode")
    """Whether to build in release mode. Same as --mixins=release."""
    dev: bool = cli.arg(None, "dev", "Always use latest from 'main' for externs")
    """Dev mode bypasses lock and tracks latest from main."""


class TargetArgs(RegistryArgs):
    """
    Arguments for the Target class.
    """

    target: str = cli.arg(
        None, "target", "The target to use", default="host-" + shell.uname().machine
    )
    """The target to use."""


@dt.dataclass
class Target(Manifest):
    """
    Represents a build target.
    """

    props: Props = dt.field(default_factory=dict)
    """Properties of the target."""
    tools: Tools = dt.field(default_factory=dict)
    """Tools available for the target."""
    routing: dict[str, str] = dt.field(default_factory=dict)
    """Routing table for component specs."""

    _hashid: Optional[str] = None
    """Cached hash ID of the target."""

    @property
    def hashid(self) -> str:
        """
        Returns a hash ID of the target.

        Returns:
            The hash ID of the target.
        """
        if self._hashid is None:
            self._hashid = utils.hash(
                (self.props, [v.to_dict() for k, v in self.tools.items()])
            )
        return self._hashid

    @property
    def builddir(self) -> str:
        """
        Returns the build directory for the target.

        Returns:
            The build directory for the target.
        """
        postfix = f"-{self.hashid[:8]}"
        if self.props.get("host"):
            postfix += f"-{str(const.HOSTID)[:8]}"
        return os.path.join(const.BUILD_DIR, f"{self.id}{postfix}")

    @staticmethod
    def use(args: TargetArgs) -> "Target":
        """
        Get the currently active target.

        Args:
            args: Target arguments.

        Returns:
            The currently active Target object.
        """
        registry = Registry.use(args)
        return registry.ensure(args.target, Target)

    def route(self, componentSpec: str):
        """
        Route a component spec to a target specific component spec.

        Args:
            componentSpec: The component spec to route.

        Returns:
            The routed component spec.
        """
        return (
            self.routing[componentSpec]
            if componentSpec in self.routing
            else componentSpec
        )


# MARK: Component --------------------------------------------------------------


@dt.dataclass
class Resolved(DataClassJsonMixin):
    """
    Represents the resolved dependencies of a component.
    """

    reason: Optional[str] = None
    """Reason why the component is not enabled, or None if it is enabled."""
    required: list[str] = dt.field(default_factory=list)
    """List of required component IDs."""
    injected: list[str] = dt.field(default_factory=list)
    """List of injected component IDs."""

    @property
    def enabled(self) -> bool:
        """
        Whether the component is enabled.

        Returns:
            True if the component is enabled, False otherwise.
        """
        return self.reason is None


@dt.dataclass
class Component(Manifest):
    """
    Represents a component in the CuteKit model.
    """

    description: str = dt.field(default="(No description)")
    """Description of the component."""
    props: Props = dt.field(default_factory=dict)
    """Properties of the component."""
    tools: Tools = dt.field(default_factory=dict)
    """Tools provided by the component."""
    enableIf: dict[str, list[str | bool | None]] = dt.field(default_factory=dict)
    """Conditions that must be met for the component to be enabled."""
    requires: list[str] = dt.field(default_factory=list)
    """List of required component specs."""
    provides: list[str] = dt.field(default_factory=list)
    """List of component specs provided by this component."""
    subdirs: list[str] = dt.field(default_factory=list)
    """List of subdirectories belonging to the component."""
    injects: list[str] = dt.field(default_factory=list)
    """List of component specs to inject into."""

    resolved: dict[str, Resolved] = dt.field(default_factory=dict)
    """Resolved dependencies of the component for each target."""

    def isEnabled(self, target: Target) -> tuple[bool, str]:
        """
        Check if the component is enabled for a given target.

        Args:
            target: The target to check against.

        Returns:
            A tuple containing a boolean indicating whether the component is enabled
            and a string containing the reason why it is not enabled (if applicable).
        """
        for k, v in self.enableIf.items():
            if k not in target.props:
                # The value is defaulted ?
                if None in v:
                    return True, ""

                _logger.info(f"Component {self.id} disabled by missing {k} in target")
                return False, f"Missing props '{k}' in target"

            elif target.props[k] not in v:
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
"""Mapping of manifest kinds to their corresponding classes."""

# MARK: Dependency resolution --------------------------------------------------

Candidate = tuple[Component, Resolved]


@dt.dataclass
class Resolver:
    """
    Resolves dependencies between components.
    """

    _registry: "Registry"
    """The registry containing the components."""
    _target: Target
    """The target for which to resolve dependencies."""
    _mappings: dict[str, list[Component]] = dt.field(default_factory=dict)
    """Mapping of component specs to their providers."""
    _baked = False
    """Whether the resolver has been baked."""

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

    def _provider(self, spec: str) -> tuple[Optional[Component], str]:
        """
        Returns the provider for a given spec.

        Args:
            spec: The component spec to find a provider for.

        Returns:
            A tuple containing the ID of the provider (if found) and a string
            containing the reason why no provider was found (if applicable).
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

        return (result[0], "")

    _cache: dict[str, Resolved] = dt.field(default_factory=dict)
    """Cache of resolved dependencies."""

    def resolve(self, spec: str, stack: list[str] = []) -> Resolved:
        """
        Resolve a given spec to a list of components.

        Args:
            what: The component spec to resolve.
            stack: The current dependency stack.

        Returns:
            A Resolved object containing the resolved dependencies.
        """
        if spec in self._cache:
            return self._cache[spec]
        resolved = self._resolve(spec, stack)
        self._cache[spec] = resolved
        return resolved

    def _resolve(self, spec: str, stack: list[str] = []) -> Resolved:
        self._bake()

        candidates = self._mappings.get(spec, [])
        if len(candidates) == 0:
            return Resolved(f"no provider for '{spec}'")

        resolved: list[tuple[Component, Resolved]] = []
        for component in candidates:
            enabled, reason = component.isEnabled(self._target)
            if not enabled:
                resolved.append(
                    (
                        component,
                        Resolved(f"component {component.id} is not enabled: {reason}"),
                    )
                )
                continue

            if component.id in stack:
                resolved.append(
                    (component, Resolved(f"circular dependency detected: {stack}"))
                )
                continue
            stack.append(spec)

            failed = False
            result: list[str] = []
            for required in component.requires:
                requiredResolved = self.resolve(required, stack + [component.id])
                if requiredResolved.reason:
                    reason = f"dependency '{required}' could not be resolved:\n{vt100.indent(requiredResolved.reason)}"
                    resolved.append((component, Resolved(reason)))
                    failed = True
                    break

                result.extend(requiredResolved.required)

            stack.pop()
            if failed:
                continue

            result.insert(0, component.id)
            resolved.append(
                (component, Resolved(required=utils.uniqPreserveOrder(result)))
            )

        viable = list(filter(lambda x: x[1].reason is None, resolved))

        if len(viable) == 0:
            triedMsg = vt100.indent(
                "\n".join(
                    map(
                        lambda x: f"tried '{x[0].id}':\n{vt100.indent(x[1].reason or '')}",
                        resolved,
                    )
                )
            )
            final = Resolved(f"no viable provider for '{spec}'\n{triedMsg}")
        elif len(viable) > 1:
            ids = list(map(lambda x: x[0].id, viable))
            final = Resolved(f"multiple providers for '{spec}': {', '.join(ids)}")
        else:
            final = viable[0][1]

        return final


# MARK: Registry ---------------------------------------------------------------

_registry: Optional["Registry"] = None


@dt.dataclass
class Registry(DataClassJsonMixin):
    """
    Represents the CuteKit model registry.
    """

    project: Project
    """The project associated with the registry."""
    manifests: dict[str, Manifest] = dt.field(default_factory=dict)
    """Dictionary of loaded manifests, keyed by their ID."""

    def _append(self, m: Manifest) -> Manifest:
        """
        Append a manifest to the model.

        Args:
            m: The manifest to append.

        Returns:
            The appended manifest.

        Raises:
            RuntimeError: If a manifest with the same ID is already loaded.
        """
        if m.id in self.manifests:
            raise RuntimeError(
                f"Duplicated manifest '{m.id}' at '{m.path}' already loaded from '{self.manifests[m.id].path}'"
            )

        self.manifests[m.id] = m
        return m

    def _extend(self, ms: list[Manifest]) -> list[Manifest]:
        """
        Append a list of manifests to the model.

        Args:
            ms: The list of manifests to append.

        Returns:
            The list of appended manifests.
        """
        return [self._append(m) for m in ms]

    def iter(self, type: Type[utils.T]) -> Generator[utils.T, None, None]:
        """
        Iterate over all manifests of a given type.

        Args:
            type: The type of manifest to iterate over.

        Yields:
            The manifest objects of the specified type.
        """

        for m in self.manifests.values():
            if isinstance(m, type):
                yield m

    def iterEnabled(self, target: Target) -> Generator[Component, None, None]:
        """
        Iterate over all enabled components for a given target.

        Args:
            target: The target to iterate over.

        Yields:
            The enabled Component objects.
        """
        for c in self.iter(Component):
            resolve = c.resolved[target.id]
            if resolve.enabled:
                yield c

    def lookup(
        self, name: str, type: Type[utils.T], includeProvides: bool = False
    ) -> Optional[utils.T]:
        """
        Lookup a manifest of a given type by name.

        Args:
            name: The name of the manifest to lookup.
            type: The type of manifest to lookup.
            includeProvides: Whether to include components that provide the given name.

        Returns:
            The manifest object, or None if no matching manifest was found.
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

        Args:
            name: The name of the manifest to ensure.
            type: The type of manifest to ensure.

        Returns:
            The manifest object.

        Raises:
            RuntimeError: If no matching manifest was found.
        """

        m = self.lookup(name, type)
        if not m:
            raise RuntimeError(f"Could not find {type.__name__} '{name}'")
        return m

    @staticmethod
    def use(args: RegistryArgs) -> "Registry":
        """
        Get the currently active registry.

        Args:
            args: Registry arguments.

        Returns:
            The currently active Registry object.
        """
        global _registry

        if _registry is not None:
            return _registry

        if args.release:
            args.mixins += ["release"]

        project = Project.use()
        _registry = Registry.load(project, args.mixins, args.props)
        return _registry

    @staticmethod
    def _loadExterns(r: "Registry", p: Project):
        """
        Load all externs for the project.

        Args:
            r: The registry to load the externs into.
            p: The project to load the externs for.
        """
        # Respect lock/dev on initial load
        r._extend(p.fetchExterns(dev=False, updateLock=False))

    @staticmethod
    def _loadManifests(r: "Registry"):
        """
        Load all manifests for each project in the registry.

        Args:
            r: The registry to load the manifests into.
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
        Resolve all dependencies for all targets.

        Args:
            r: The registry to load the dependencies into.
            mixins: The list of mixins to apply.
            props: The properties to set.
        """

        for target in r.iter(Target):
            target.props |= props
            if "version" not in target.props:
                target.props["version"] = r.project.version

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
        Load the model for a given project, applying mixins and props.

        Args:
            project: The project to load the model for.
            mixins: The list of mixins to apply.
            props: The properties to set.

        Returns:
            The loaded Registry object.
        """
        _logger.info(f"Loading model for project '{project.id}'")

        r = Registry(project)
        r._append(project)

        Registry._loadExterns(r, project)
        Registry._loadManifests(r)
        Registry._loadDependencies(r, mixins, props)

        return r


@cli.command("model/list", "List all components and targets")
def _(args: TargetArgs):
    """
    List all components and targets in the model.
    """
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


@cli.command("model/dump", "Dump the model")
def _(args: TargetArgs):
    """
    Dump the model as JSON.
    """
    registry = Registry.use(args)
    print("[")
    for m in registry.manifests.values():
        print(m.to_json(indent=2), end="")
        print(",")
    print("]")


@cli.command("model/mount", "Mount this project to the global extern directory")
def _(args: TargetArgs):
    """
    Mount this project to the global extern directory
    """
    project = Project.use()
    projectDir = os.path.abspath(project.dirname())
    globalExternDir = os.path.join(const.GLOBAL_EXTERN_DIR, project.id)
    if os.path.exists(globalExternDir):
        shell.exec("rm", globalExternDir)
    shell.mkdir(os.path.dirname(globalExternDir))
    shell.exec("ln", "-s", projectDir, globalExternDir)
    print(f"Mounted {projectDir} to {globalExternDir}")


@cli.command("model/unmount", "Unmount this project from the global extern directory")
def _(args: TargetArgs):
    """
    Unmount this project from the global extern directory
    """
    project = Project.use()
    globalExternDir = os.path.join(const.GLOBAL_EXTERN_DIR, project.id)
    shell.exec("rm", globalExternDir)
    print(f"Unmounted {globalExternDir}")


# MARK: Lock commands ----------------------------------------------------------


@cli.command("model/update", "Update project.lock to latest commits and checkout")
def _(args: RegistryArgs):
    """
    Update all externs to latest of their configured ref and write project.lock.
    """
    project = Project.use()
    project.fetchExterns(dev=False, updateLock=True)
    print("Updated project.lock and checked out latest commits.")


@cli.command("model/verify", "Verify externs match project.lock")
def _(args: RegistryArgs):
    """
    Verify that extern checkouts match the lockfile. Exits non-zero on mismatch.
    """
    project = Project.use()
    n = project.verifyExterns()
    if n > 0:
        raise RuntimeError(f"lock verification failed with {n} error(s)")
    print("All externs match the lock. Carry on.")
