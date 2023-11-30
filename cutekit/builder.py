import os
import logging
import dataclasses as dt

from pathlib import Path
from typing import Callable, TextIO, Union

from . import shell, rules, model, ninja, const, cli

_logger = logging.getLogger(__name__)


@dt.dataclass
class TargetScope:
    registry: model.Registry
    target: model.Target

    @staticmethod
    def use(args: cli.Args) -> "TargetScope":
        registry = model.Registry.use(args)
        target = model.Target.use(args)
        return TargetScope(registry, target)

    def openComponentScope(self, c: model.Component):
        return ComponentScope(self.registry, self.target, c)


@dt.dataclass
class ComponentScope(TargetScope):
    component: model.Component

    def openComponentScope(self, c: model.Component):
        return ComponentScope(self.registry, self.target, c)

    def openProductScope(self, path: Path):
        return ProductScope(self.registry, self.target, self.component, path)


@dt.dataclass
class ProductScope(ComponentScope):
    path: Path


# --- Variables -------------------------------------------------------------- #

Compute = Callable[[TargetScope], str]
_vars: dict[str, Compute] = {}


def var(name: str) -> Callable[[Compute], Compute]:
    def decorator(func: Compute):
        _vars[name] = func
        return func

    return decorator


@var("buildir")
def _computeBuildir(scope: TargetScope) -> str:
    return scope.target.builddir


@var("hashid")
def _computeHashid(scope: TargetScope) -> str:
    return scope.target.hashid


@var("cincs")
def _computeCinc(scope: TargetScope) -> str:
    res = set()

    for c in scope.registry.iterEnabled(scope.target):
        if "cpp-root-include" in c.props:
            res.add(c.dirname())
        elif c.type == model.Kind.LIB:
            res.add(str(Path(c.dirname()).parent))

    return " ".join(set(map(lambda i: f"-I{i}", res)))


@var("cdefs")
def _computeCdef(scope: TargetScope) -> str:
    res = set()

    def sanatize(s: str) -> str:
        return s.lower().replace(" ", "_").replace("-", "_").replace(".", "_")

    for k, v in scope.target.props.items():
        if isinstance(v, bool):
            if v:
                res.add(f"-D__ck_{sanatize(k)}__")
        else:
            res.add(f"-D__ck_{sanatize(k)}_{sanatize(str(v))}__")
            res.add(f"-D__ck_{sanatize(k)}_value={str(v)}")

    return " ".join(res)


def buildpath(scope: ComponentScope, path) -> Path:
    return Path(scope.target.builddir) / scope.component.id / path


# --- Compilation ------------------------------------------------------------ #


def subdirs(scope: ComponentScope) -> list[str]:
    registry = scope.registry
    target = scope.target
    component = scope.component
    result = [component.dirname()]

    for subs in component.subdirs:
        result.append(os.path.join(component.dirname(), subs))

    for inj in component.resolved[target.id].injected:
        injected = registry.lookup(inj, model.Component)
        assert injected is not None  # model.Resolver has already checked this
        result.extend(subdirs(scope))

    return result


def wilcard(scope: ComponentScope, wildcards: list[str]) -> list[str]:
    return shell.find(subdirs(scope), list(wildcards), recusive=False)


def compile(
    w: ninja.Writer, scope: ComponentScope, rule: str, srcs: list[str]
) -> list[str]:
    res: list[str] = []
    for src in srcs:
        rel = Path(src).relative_to(scope.component.dirname())
        dest = buildpath(scope, "obj") / rel.with_suffix(".o")
        t = scope.target.tools[rule]
        w.build(str(dest), rule, inputs=src, order_only=t.files)
        res.append(str(dest))
    return res


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
        dest = buildpath(scope, "res") / rel
        w.build(str(dest), "cp", r)
        res.append(str(dest))
    return res


# --- Linking ---------------------------------------------------------------- #


def outfile(scope: ComponentScope) -> str:
    if scope.component.type == model.Kind.LIB:
        return str(buildpath(scope, f"lib/{scope.component.id}.a"))
    else:
        return str(buildpath(scope, f"bin/{scope.component.id}.out"))


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


def link(
    w: ninja.Writer,
    scope: ComponentScope,
) -> str:
    w.newline()
    out = outfile(scope)

    objs = []
    objs += compile(w, scope, "cc", wilcard(scope, ["*.c"]))
    objs += compile(
        w,
        scope,
        "cxx",
        wilcard(scope, ["*.cpp", "*.cc", "*.cxx"]),
    )
    objs += compile(
        w,
        scope,
        "as",
        wilcard(scope, ["*.s", "*.asm", "*.S"]),
    )

    res = compileRes(w, scope)
    libs = collectLibs(scope)
    if scope.component.type == model.Kind.LIB:
        w.build(out, "ar", objs, implicit=res)
    else:
        w.build(out, "ld", objs + libs, implicit=res)
    return out


# --- Phony ------------------------------------------------------------------ #


def all(w: ninja.Writer, scope: TargetScope) -> list[str]:
    all: list[str] = []
    for c in scope.registry.iterEnabled(scope.target):
        all.append(link(w, scope.openComponentScope(c)))
    w.build("all", "phony", all)
    w.default("all")
    return all


def gen(out: TextIO, scope: TargetScope):
    w = ninja.Writer(out)

    w.comment("File generated by the build system, do not edit")
    w.newline()

    w.separator("Variables")
    for name, compute in _vars.items():
        w.variable(name, compute(scope))
    w.newline()

    w.separator("Tools")

    for i in scope.target.tools:
        tool = scope.target.tools[i]
        rule = rules.rules[i]
        w.variable(i, tool.cmd)
        w.variable(i + "flags", " ".join(rule.args + tool.args))
        w.rule(
            i,
            f"{tool.cmd} {rule.rule.replace('$flags',f'${i}flags')}",
            depfile=rule.deps,
        )
        w.newline()

    w.separator("Build")

    all(w, scope)


def build(
    scope: TargetScope,
    components: Union[list[model.Component], model.Component, None] = None,
) -> list[ProductScope]:
    all = False
    shell.mkdir(scope.target.builddir)
    ninjaPath = os.path.join(scope.target.builddir, "build.ninja")

    if not os.path.exists(ninjaPath):
        with open(ninjaPath, "w") as f:
            gen(f, scope)

    if components is None:
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

    # shell.exec("ninja", "-f", ninjaPath, *(outs if not all else []))

    return products


# --- Commands --------------------------------------------------------------- #


@cli.command("b", "build", "Build/Run/Clean a component or all components")
def buildCmd(args: cli.Args):
    pass


@cli.command("b", "build/build", "Build a component or all components")
def buildBuildCmd(args: cli.Args):
    scope = TargetScope.use(args)
    componentSpec = args.consumeArg()
    component = None
    if componentSpec is not None:
        component = scope.registry.lookup(componentSpec, model.Component)
    build(scope, component)[0]


@cli.command("r", "build/run", "Run a component")
def buildRunCmd(args: cli.Args):
    scope = TargetScope.use(args)
    debug = args.consumeOpt("debug", False) is True

    componentSpec = args.consumeArg() or "__main__"
    component = scope.registry.lookup(
        componentSpec, model.Component, includeProvides=True
    )
    if component is None:
        raise RuntimeError(f"Component {componentSpec} not found")

    product = build(scope, component)[0]

    os.environ["CK_TARGET"] = product.target.id
    os.environ["CK_BUILDDIR"] = product.target.builddir
    os.environ["CK_COMPONENT"] = product.component.id

    shell.exec(*(["lldb", "-o", "run"] if debug else []), str(product.path), *args.args)


@cli.command("t", "build/test", "Run all test targets")
def buildTestCmd(args: cli.Args):
    # This is just a wrapper around the `run` command that try
    # to run a special hook component named __tests__.
    args.args.insert(0, "__tests__")
    buildRunCmd(args)


@cli.command("d", "build/debug", "Debug a component")
def buildDebugCmd(args: cli.Args):
    # This is just a wrapper around the `run` command that
    # always enable debug mode.
    args.opts["debug"] = True
    buildRunCmd(args)


@cli.command("c", "build/clean", "Clean build files")
def buildCleanCmd(args: cli.Args):
    model.Project.use(args)
    shell.rmrf(const.BUILD_DIR)


@cli.command("n", "build/nuke", "Clean all build files and caches")
def buildNukeCmd(args: cli.Args):
    model.Project.use(args)
    shell.rmrf(const.PROJECT_CK_DIR)
