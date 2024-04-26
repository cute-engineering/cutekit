import os
import logging
import dataclasses as dt

from pathlib import Path
from typing import Callable, Literal, TextIO, Union

from . import cli, shell, rules, model, ninja, const, vt100, mixins

_logger = logging.getLogger(__name__)


@dt.dataclass
class Scope:
    registry: model.Registry

    @staticmethod
    def use(args: model.RegistryArgs) -> "Scope":
        registry = model.Registry.use(args)
        return Scope(registry)

    def key(self) -> str:
        return self.registry.project.id

    def openTargetScope(self, t: model.Target):
        return TargetScope(self.registry, t)


@dt.dataclass
class TargetScope(Scope):
    registry: model.Registry
    target: model.Target

    @staticmethod
    def use(args: model.TargetArgs) -> "TargetScope":  # type: ignore[override]
        registry = model.Registry.use(args)
        target = model.Target.use(args)
        return TargetScope(registry, target)

    def key(self) -> str:
        return super().key() + "/" + self.target.id + "/" + self.target.hashid

    def openComponentScope(self, c: model.Component):
        return ComponentScope(self.registry, self.target, c)


@dt.dataclass
class ComponentScope(TargetScope):
    component: model.Component

    def key(self) -> str:
        return super().key() + "/" + self.component.id

    def openComponentScope(self, c: model.Component):
        return ComponentScope(self.registry, self.target, c)

    def openProductScope(self, path: Path):
        return ProductScope(self.registry, self.target, self.component, path)


@dt.dataclass
class ProductScope(ComponentScope):
    path: Path


# --- Variables -------------------------------------------------------------- #

Compute = Callable[[TargetScope], list[str]]
_vars: dict[str, Compute] = {}


def var(name: str) -> Callable[[Compute], Compute]:
    def decorator(func: Compute):
        _vars[name] = func
        return func

    return decorator


@var("builddir")
def _computeBuilddir(scope: TargetScope) -> list[str]:
    """
    This variable is needed by ninja to know where to put
    the .ninja_log file.
    """
    return [scope.target.builddir]


@var("hashid")
def _computeHashid(scope: TargetScope) -> list[str]:
    return [scope.target.hashid]


@var("cincs")
def _computeCinc(scope: TargetScope) -> list[str]:
    res = set()

    for c in scope.registry.iterEnabled(scope.target):
        if "cpp-root-include" in c.props:
            res.add(c.dirname())
        elif "cpp-excluded" in c.props:
            pass
        elif c.type == model.Kind.LIB:
            res.add(str(Path(c.dirname()).parent))

    return sorted(map(lambda i: f"-I{i}", res))


@var("cdefs")
def _computeCdef(scope: TargetScope) -> list[str]:
    res = set()

    def sanatize(s: str) -> str:
        TO_REPLACE = [" ", "-", "."]  # -> "_"
        for r in TO_REPLACE:
            s = s.replace(r, "_")
        return "".join(filter(lambda c: c.isalnum() or c == "_", s))

    for k, v in scope.target.props.items():
        if isinstance(v, bool):
            if v:
                res.add(f"-D__ck_{sanatize(k)}__")
        else:
            res.add(f"-D__ck_{sanatize(k)}_{sanatize(str(v))}__")
            res.add(f"-D__ck_{sanatize(k)}_value={str(v)}")

    return sorted(res)


def buildpath(scope: ComponentScope, path) -> Path:
    return Path(scope.target.builddir) / scope.component.id / path


# --- Compilation ------------------------------------------------------------ #


def subdirs(scope: ComponentScope) -> list[str]:
    component = scope.component
    result = [component.dirname()]

    for subs in component.subdirs:
        result.append(os.path.join(component.dirname(), subs))

    return result


def wilcard(scope: ComponentScope, wildcards: list[str]) -> list[str]:
    return shell.find(subdirs(scope), list(wildcards), recusive=False)


def compile(
    w: ninja.Writer | None, scope: ComponentScope, rule: str, srcs: list[str]
) -> list[str]:
    res: list[str] = []
    for src in srcs:
        rel = Path(src).relative_to(scope.component.dirname())
        dest = buildpath(scope, path="__obj__") / rel.with_suffix(rel.suffix + ".o")
        t = scope.target.tools[rule]
        if w:
            w.build(
                str(dest),
                rule,
                inputs=src,
                order_only=t.files,
                variables={
                    "ck_target": scope.target.id,
                    "ck_component": scope.component.id,
                },
            )
        res.append(str(dest))
    return res


def compileObjs(w: ninja.Writer, scope: ComponentScope) -> list[str]:
    objs = []
    for rule in rules.rules.values():
        if rule.id not in ["cp", "ld", "ar"]:
            objs += compile(w, scope, rule.id, srcs=wilcard(scope, rule.fileIn))
    return objs


# --- Ressources ------------------------------------------------------------- #


def listRes(component: model.Component) -> list[str]:
    return shell.find(str(component.subpath("res")))


def compileRes(
    w: ninja.Writer,
    scope: ComponentScope,
) -> list[str]:
    res: list[str] = []
    for r in listRes(scope.component):
        rel = Path(r).relative_to(scope.component.subpath("res"))
        dest = buildpath(scope, "__res__") / rel
        w.build(
            str(dest),
            "cp",
            r,
            variables={
                "ck_target": scope.target.id,
                "ck_component": scope.component.id,
            },
        )
        res.append(str(dest))
    return res


# --- Linking ---------------------------------------------------------------- #


def outfile(scope: ComponentScope) -> str:
    if scope.component.type == model.Kind.LIB:
        return str(buildpath(scope, f"__lib__/{scope.component.id}.a"))
    else:
        return str(buildpath(scope, f"__bin__/{scope.component.id}.out"))


def collectLibs(
    scope: ComponentScope,
) -> list[str]:
    res: list[str] = []
    for r in scope.component.resolved[scope.target.id].required:
        req = scope.registry.lookup(r, model.Component)
        assert req is not None  # model.Resolver has already checked this

        if r == scope.component.id:
            continue
        if not req.type == model.Kind.LIB:
            raise RuntimeError(f"Component {r} is not a library")
        res.append(outfile(scope.openComponentScope(req)))

    return res


def collectInjectedObjs(scope: ComponentScope) -> list[str]:
    res: list[str] = []
    for r in scope.component.resolved[scope.target.id].injected:
        req = scope.registry.lookup(r, model.Component)
        assert req is not None  # model.Resolver has already checked this

        if r == scope.component.id:
            continue
        if not req.type == model.Kind.LIB:
            raise RuntimeError(f"Component {r} is not a library")
        res.extend(compileObjs(None, scope.openComponentScope(req)))

    return res


def link(
    w: ninja.Writer,
    scope: ComponentScope,
) -> str:
    w.newline()
    out = outfile(scope)

    res = compileRes(w, scope)
    objs = compileObjs(w, scope)
    if scope.component.type == model.Kind.LIB:
        w.build(
            out,
            "ar",
            objs,
            implicit=res,
            variables={
                "ck_target": scope.target.id,
                "ck_component": scope.component.id,
            },
        )
    else:
        injectedObjs = collectInjectedObjs(scope)
        libs = collectLibs(scope)
        w.build(
            out,
            "ld",
            objs + libs,
            variables={
                "objs": " ".join(objs + injectedObjs),
                "libs": " ".join(libs),
                "ck_target": scope.target.id,
                "ck_component": scope.component.id,
            },
            implicit=res,
        )
    return out


# --- Phony ------------------------------------------------------------------ #


def all(w: ninja.Writer, scope: TargetScope) -> list[str]:
    all: list[str] = []
    for c in scope.registry.iterEnabled(scope.target):
        all.append(link(w, scope.openComponentScope(c)))
    w.build("all", "phony", all)
    w.default("all")
    return all


def applyExtraProps(scope: TargetScope, name: str, var: list[str]) -> list[str]:
    target: model.Target = scope.target
    extra = target.props.get(f"ck-{name}-extra", None)
    if extra:
        var += extra.split(" ")
    override = target.props.get(f"ck-{name}-override")
    if override:
        var = override.split(" ")
    return var


def gen(out: TextIO, scope: TargetScope):
    w = ninja.Writer(out)
    target: model.Target = scope.target

    w.comment("File generated by the build system, do not edit")
    w.newline()

    w.separator("Variables")
    for name, compute in _vars.items():
        w.variable(name, applyExtraProps(scope, name, compute(scope)))
    w.newline()

    w.separator("Tools")

    for i in target.tools:
        tool = target.tools[i]
        rule = rules.rules[i]
        w.variable(i, tool.cmd)
        w.variable(
            i + "flags",
            " ".join(applyExtraProps(scope, i + "flags", rule.args + tool.args)),
        )
        w.rule(
            i,
            f"{tool.cmd} {(tool.rule or rule.rule).replace('$flags',f'${i}flags')}",
            description=f"{vt100.BLUE}$ck_target{vt100.RESET}/{vt100.CYAN}$ck_component{vt100.RESET}: {vt100.YELLOW}{i} {vt100.FAINT + vt100.WHITE}$out...{vt100.RESET}",
            depfile=rule.deps,
        )
        w.newline()

    w.separator("Build")

    all(w, scope)


def build(
    scope: TargetScope,
    components: Union[list[model.Component], model.Component, Literal["all"]] = "all",
) -> list[ProductScope]:
    all = False
    shell.mkdir(scope.target.builddir)
    ninjaPath = os.path.join(scope.target.builddir, "build.ninja")

    with open(ninjaPath, "w") as f:
        gen(f, scope)

    if components == "all":
        all = True
        components = list(scope.registry.iterEnabled(scope.target))

    if isinstance(components, model.Component):
        components = [components]

    products: list[ProductScope] = []
    for c in components:
        s = scope.openComponentScope(c)
        r = c.resolved[scope.target.id]
        if not r.enabled:
            raise RuntimeError(f"Component {c.id} is disabled: {r.reason}")

        products.append(s.openProductScope(Path(outfile(scope.openComponentScope(c)))))

    outs = list(map(lambda p: str(p.path), products))

    shell.exec("ninja", "-f", ninjaPath, *(outs if not all else []))

    return products


# --- Commands --------------------------------------------------------------- #


@cli.command("b", "builder", "Build/Run/Clean a component or all components")
def _():
    pass


class BuildArgs(model.TargetArgs):
    component: str = cli.operand("component", "Component to build", default="__main__")
    universe: bool = cli.arg(None, "universe", "Does it for all targets")


@cli.command("b", "builder/build", "Build a component or all components")
def _(args: BuildArgs):
    if args.universe:
        registry = model.Registry.use(args)
        for target in registry.iter(model.Target):
            scope = TargetScope(registry, target)
            component = None
            if args.component is not None:
                component = scope.registry.lookup(args.component, model.Component)
            build(scope, component if component is not None else "all")[0]
    else:
        scope = TargetScope.use(args)
        component = None
        if args.component is not None:
            component = scope.registry.lookup(args.component, model.Component)
        build(scope, component if component is not None else "all")[0]


class RunArgs(BuildArgs, shell.DebugArgs, shell.ProfileArgs):
    debug: bool = cli.arg("d", "debug", "Attach a debugger")
    profile: bool = cli.arg("p", "profile", "Profile the execution")
    args: list[str] = cli.extra("args", "Arguments to pass to the component")


@cli.command("r", "builder/run", "Run a component or __main__ if not specified")
def runCmd(args: RunArgs):
    if args.debug:
        args.mixins.append("debug")
        args.props |= {"debug": True}

    if args.component is None:
        args.component = "__main__"

    scope = TargetScope.use(args)

    component = scope.registry.lookup(
        args.component, model.Component, includeProvides=True
    )
    if component is None:
        raise RuntimeError(f"Component {args.component} not found")

    product = build(scope, component)[0]

    os.environ["CK_TARGET"] = product.target.id
    os.environ["CK_BUILDDIR"] = product.target.builddir
    os.environ["CK_COMPONENT"] = product.component.id

    command = [str(product.path), *args.args]

    if args.debug:
        shell.debug(command, debugger=args.debugger, wait=args.wait)
    elif args.profile:
        shell.profile(command, what=args.what, rate=args.rate)
    else:
        shell.exec(*command)


@cli.command("t", "builder/test", "Run all test targets")
def _(args: RunArgs):
    # This is just a wrapper around the `run` command that try
    # to run a special hook component named __tests__.
    args.component = "__tests__"
    runCmd(args)


@cli.command("d", "builder/debug", "Debug a component")
def _(args: RunArgs):
    # This is just a wrapper around the `run` command that
    # always enable debug mode.
    args.debug = True
    runCmd(args)


@cli.command("c", "builder/clean", "Clean build files")
def _():
    model.Project.use()
    shell.rmrf(const.BUILD_DIR)


@cli.command("n", "builder/nuke", "Clean all build files and caches")
def _():
    model.Project.use()
    shell.rmrf(const.PROJECT_CK_DIR)


@cli.command("m", "builder/mixins", "List all available mixins")
def _():
    vt100.title("Mixins")
    print(vt100.indent(vt100.wordwrap(", ".join(mixins.mixins.keys()))))
    print()
