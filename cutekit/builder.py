import os
import logging
import dataclasses as dt
import json

from pathlib import Path
import platform
from typing import Callable, Literal, TextIO, Union

from . import cli, shell, rules, model, ninja, const

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

    @property
    def targets(self):
        for t in self.registry.iter(model.Target):
            yield self.openTargetScope(t)

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

    def buildpath(self, path: str | Path) -> Path:
        return Path(self.target.builddir) / path

    @property
    def components(self):
        for c in self.registry.iterEnabled(self.target):
            yield self.openComponentScope(c)

    def openComponentScope(self, c: model.Component):
        return ComponentScope(self.registry, self.target, c)

    def up(self):
        return Scope(self.registry)


@dt.dataclass
class ComponentScope(TargetScope):
    component: model.Component

    def key(self) -> str:
        return super().key() + "/" + self.component.id

    def openComponentScope(self, c: model.Component):
        return ComponentScope(self.registry, self.target, c)

    def openProductScope(self, path: Path):
        return ProductScope(self.registry, self.target, self.component, path)

    def subdirs(self) -> list[str]:
        component = self.component
        result = [component.dirname()]
        for subs in component.subdirs:
            result.append(os.path.join(component.dirname(), subs))
        return result

    def wilcard(self, wildcards: list[str] | str) -> list[str]:
        if isinstance(wildcards, str):
            wildcards = [wildcards]
        return shell.find(self.subdirs(), wildcards, recusive=False)

    def buildpath(self, path: str | Path) -> Path:
        return Path(self.target.builddir) / self.component.id / path

    def genpath(self, path: str | Path) -> Path:
        return Path(const.GENERATED_DIR) / self.component.id / path

    def useEnv(self):
        os.environ["CK_TARGET"] = self.target.id
        os.environ["CK_BUILDDIR"] = str(Path(self.target.builddir).resolve())
        os.environ["CK_COMPONENT"] = self.component.id

    def up(self):
        return TargetScope(self.registry, self.target)


@dt.dataclass
class ProductScope(ComponentScope):
    path: Path

    def popen(self, *args):
        self.useEnv()
        return shell.popen(str(self.path), *args)

    def exec(self, *args):
        self.useEnv()
        return shell.exec(str(self.path), *args)


# MARK: Variables --------------------------------------------------------------

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

    includeAliases = os.path.join(const.GENERATED_DIR, "__aliases__")
    includeGenerated = os.path.join(const.GENERATED_DIR)
    res.add(includeAliases)
    res.add(includeGenerated)

    for c in scope.registry.iterEnabled(scope.target):
        if "cpp-root-include" in c.props:
            res.add(c.dirname())
        elif "cpp-excluded" in c.props:
            pass
        elif c.type == model.Kind.LIB:
            res.add(str(Path(c.dirname()).parent))

    incs = sorted(map(lambda i: f"-I{i}", res))
    if scope.target.props["host"] and platform.system() == "Darwin":
        incs.insert(
            0,
            f"-isysroot {shell.popen('xcrun', '--sdk', 'macosx', '--show-sdk-path').strip()}",
        )
    return incs


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


# MARK: Compilation ------------------------------------------------------------


class CxxModmapArgs:
    obj: str = cli.operand("obj", "Object file")
    dir: str = cli.arg("d", "dir", "Build directory")
    deps: str = cli.arg("d", "deps", "Dependencies file")


# https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2022/p1689r5.html


def p1689Query(data, query, *args):
    for d in data:
        for r in d["rules"]:
            res = query(r, *args)
            if res is not None:
                return res
    return None


def p1689Resolve(obj: str, depFile: str) -> tuple[str | None, set[str]]:
    with open(depFile, "r") as f:
        data = json.load(f)

        queue = []
        needed: set[str] = set()

        def queryLogicalName(rule: dict, output: str):
            if rule["primary-output"] == output:
                if "requires" in rule:
                    for r in rule["requires"]:
                        queue.append(r["logical-name"])
                if "provides" in rule:
                    provided = rule["provides"][0]
                    if provided["is-interface"]:
                        return provided["logical-name"]
            return None

        logicalName = p1689Query(data, queryLogicalName, obj)

        while queue:
            current = queue.pop(0)
            if current in needed:
                continue
            needed.add(current)

            def queryModuleMap(rule: dict, current: str):
                if "provides" in rule:
                    for r in rule["provides"]:
                        if r["logical-name"] == current and "requires" in rule:
                            for r in rule["requires"]:
                                queue.append(r["logical-name"])

            p1689Query(data, queryModuleMap, current)

        return logicalName, needed


@cli.command("tools", "Tools used by the build system")
def _():
    pass


@cli.command("tools/cxx-modmap", "Generate a module map for C++")
def _(args: CxxModmapArgs):
    os.makedirs(args.dir, exist_ok=True)
    logicalName, needed = p1689Resolve(args.obj, args.deps)
    if logicalName is not None:
        print("-x c++-module")
        print(
            f"-fmodule-output={os.path.join(args.dir, logicalName).replace(':', '__')}.pcm"
        )
    for n in needed:
        print(f"-fmodule-file={n}={os.path.join(args.dir, n).replace(':', '__')}.pcm")


class CxxDyndepArgs:
    dir: str = cli.arg("d", "dir", "Build directory")
    deps: str = cli.arg("d", "deps", "Dependencies file")


@cli.command("tools/cxx-dyndep", "Generate a dynamic dependency file for C++")
def _(args: CxxDyndepArgs):
    with open(args.deps, "r") as f:
        data = json.load(f)

    print("ninja_dyndep_version = 1.0")
    print()

    for d in data:
        for rule in d.get("rules", []):
            record = f"build {rule['primary-output']}"

            firstProvides = True
            for p in rule.get("provides", []):
                if p["is-interface"]:
                    if firstProvides:
                        record += " | "
                        firstProvides = False
                    else:
                        record += " "
                    record += f"{os.path.join(args.dir, p['logical-name']).replace(':', '__')}.pcm"

            record += " : dyndep"

            firstRequires = True
            for r in rule.get("requires", []):
                if firstRequires:
                    record += " | "
                    firstRequires = False
                else:
                    record += " "
                record += f"{os.path.join(args.dir, r['logical-name']).replace(':', '__')}.pcm"

            print(record)
            print("  restat = 1")
            print()


def compileSrcs(
    w: ninja.Writer | None, scope: ComponentScope, rule: rules.Rule, srcs: list[str]
) -> list[str]:
    res: list[str] = []
    for src in srcs:
        rel = Path(src).relative_to(scope.component.dirname())
        dest = scope.buildpath(path="__obj__") / rel.with_suffix(
            rel.suffix + rule.fileOut[1:]
        )
        obj = str(scope.buildpath(path="__obj__") / rel.with_suffix(rel.suffix + ".o"))
        modmap = str(dest) + ".modmap"
        dyndep = str(scope.up().buildpath("modules.dd"))
        t = scope.target.tools[rule.id]

        variables = {}
        if rule.id == "cxx-scan":
            variables["obj"] = obj

        implicit = [*t.files]
        orderOnly = []
        if rule.id == "cxx":
            implicit.append(modmap)
            orderOnly.append(dyndep)

            if not scope.target.props.get("database", False):
                variables["modmap"] = "@" + modmap

        if w:
            if rule.id == "cxx":
                w.build(
                    modmap,
                    "cxx-modmap",
                    src,
                    order_only=[str(scope.up().buildpath("modules.dd"))],
                    variables={
                        "ck_target": scope.target.id,
                        "ck_component": scope.component.id,
                        "obj": obj,
                    },
                )

            w.build(
                str(dest),
                rule.id,
                inputs=src,
                implicit=implicit,
                order_only=orderOnly,
                dyndep=dyndep if rule.id == "cxx" else None,
                variables={
                    "ck_target": scope.target.id,
                    "ck_component": scope.component.id,
                    **variables,
                },
            )
        res.append(str(dest))
    return res


def compileObjs(
    w: ninja.Writer | None, scope: ComponentScope
) -> tuple[list[str], list[str]]:
    objs = []
    ddi = []
    for rule in rules.rules.values():
        if rule.id == "cxx-scan":
            ddi += compileSrcs(w, scope, rule, srcs=scope.wilcard(rule.fileIn))
        elif rule.id not in ["cp", "ld", "ar", "cxx-collect", "cxx-modmap"]:
            objs += compileSrcs(w, scope, rule, srcs=scope.wilcard(rule.fileIn))
    return objs, ddi


# MARK: Ressources -------------------------------------------------------------


def listRes(component: model.Component) -> list[str]:
    return shell.find(str(component.subpath("res")))


def compileRes(
    w: ninja.Writer,
    scope: ComponentScope,
) -> list[str]:
    res: list[str] = []
    for r in listRes(scope.component):
        rel = Path(r).relative_to(scope.component.subpath("res"))
        dest = scope.buildpath("__res__") / rel
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


# MARK: Linking ----------------------------------------------------------------


def outfile(scope: ComponentScope) -> str:
    sharedExt = "so"
    staticExt = "a"
    exeExt = "out"
    sysName = scope.target.props.get("sys", "unknown").lower()

    if sysName == "windows":
        sharedExt = "dll"
        staticExt = "lib"
        exeExt = "exe"
    elif sysName == "darwin":
        sharedExt = "dylib"
        staticExt = "a"
        exeExt = "out"

    if scope.component.type == model.Kind.LIB:
        if scope.component.props.get("shared", False):
            return str(scope.buildpath(f"__lib__/{scope.component.id}.{sharedExt}"))
        else:
            return str(scope.buildpath(f"__lib__/{scope.component.id}.{staticExt}"))
    else:
        return str(scope.buildpath(f"__bin__/{scope.component.id}.{exeExt}"))


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

        objs, _ = compileObjs(None, scope.openComponentScope(req))

        res.extend(objs)

    return res


def link(
    w: ninja.Writer,
    scope: ComponentScope,
) -> tuple[str, list[str]]:
    w.newline()
    out = outfile(scope)

    res = compileRes(w, scope)
    objs, ddi = compileObjs(w, scope)

    if scope.component.type == model.Kind.LIB:
        if scope.component.props.get("shared", False):
            injectedObjs = collectInjectedObjs(scope)
            libs = collectLibs(scope)
            w.build(
                out,
                "ld-shared",
                objs + libs,
                variables={
                    "objs": " ".join(objs + injectedObjs),
                    "libs": " ".join(libs),
                    "ck_target": scope.target.id,
                    "ck_component": scope.component.id,
                },
                implicit=res,
            )
        else:
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
    return out, ddi


# MARK: Phony ------------------------------------------------------------------


def all(w: ninja.Writer, scope: TargetScope) -> list[str]:
    all: list[str] = []
    ddis: list[str] = []
    for c in scope.registry.iterEnabled(scope.target):
        out, ddi = link(w, scope.openComponentScope(c))
        ddis.extend(ddi)
        all.append(out)

    modulesDdi = str(scope.buildpath("modules.ddi"))
    w.build(modulesDdi, "cxx-collect", ddis)

    modulesDd = str(scope.buildpath("modules.dd"))
    w.build(
        modulesDd,
        "cxx-dyndep",
        modulesDdi,
        variables={
            "restat": "1",
        },
    )

    all = [modulesDd] + all

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
            f"{tool.cmd} {(tool.rule or rule.rule).replace('$flags', f'${i}flags')}",
            description=f"$ck_target/$ck_component: {i} $out...",
            deps="gcc" if i in ["cxx", "cc"] else None,
            depfile=rule.deps,
        )
        w.newline()

    w.separator("Build")

    all(w, scope)


def build(
    scope: TargetScope,
    components: Union[list[model.Component], model.Component, Literal["all"]] = "all",
    generateCompilationDb: bool = False,
) -> list[ProductScope]:
    all = False
    if generateCompilationDb:
        scope.target.props["database"] = True

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

    ninjaCmd = [
        "ninja",
        "-f",
        ninjaPath,
        *(outs if not all else []),
    ]

    if generateCompilationDb:
        database = shell.popen(*ninjaCmd, "-t", "compdb", "cc", "cxx")
        with open("compile_commands.json", "w") as f:
            f.write(database)
    else:
        shell.exec(*ninjaCmd)

    return products


# MARK: Commands ---------------------------------------------------------------


class BuildArgs(model.TargetArgs):
    component: str = cli.operand("component", "Component to build", default="__main__")
    universe: bool = cli.arg(None, "universe", "Does it for all targets")
    database: bool = cli.arg(
        None,
        "database",
        "Generate compilation database (compile_commands.json)",
    )


@cli.command("build", "Build a component or all components")
def _(args: BuildArgs):
    if args.universe:
        registry = model.Registry.use(args)
        for target in registry.iter(model.Target):
            scope = TargetScope(registry, target)
            component = None
            if args.component is not None:
                component = scope.registry.lookup(args.component, model.Component)
            build(
                scope,
                component if component is not None else "all",
            )[0]
    else:
        scope = TargetScope.use(args)
        component = None
        if args.component is not None:
            component = scope.registry.lookup(args.component, model.Component)
        build(
            scope,
            component if component is not None else "all",
            generateCompilationDb=args.database,
        )[0]


class RunArgs(BuildArgs, shell.DebugArgs, shell.ProfileArgs):
    profile: bool = cli.arg("p", "profile", "Profile the execution")
    args: list[str] = cli.extra("args", "Arguments to pass to the component")
    restoreCwd: bool = cli.arg(
        "c", "restore-cwd", "Restore the current working directory", default=True
    )


@cli.command("run", "Run a component or __main__ if not specified")
def runCmd(args: RunArgs):
    if args.component is None:
        args.component = "__main__"

    scope = TargetScope.use(args)

    if args.component in scope.target.routing:
        args.component = scope.target.routing[args.component]

    component = scope.registry.lookup(
        args.component, model.Component, includeProvides=True
    )

    if component is None:
        raise RuntimeError(f"Component {args.component} not found")

    if component.type == model.Kind.LIB:
        component = scope.registry.lookup(
            args.component + ".main", model.Component, includeProvides=True
        )

    if component is None:
        raise RuntimeError(f"No entry point found for {args.component}")

    product = build(scope, component)[0]

    product.useEnv()
    command = [str(product.path.resolve()), *args.args]

    if args.restoreCwd:
        shell.restoreCwd()

    if args.debug:
        shell.debug(command, debugger=args.debugger, wait=args.wait)
    elif args.profile:
        shell.profile(command, what=args.what, rate=args.rate)
    else:
        shell.exec(*command)


@cli.command("test", "Run all test targets")
def _(args: RunArgs):
    # This is just a wrapper around the `run` command that try
    # to run a special hook component named __tests__.
    args.component = "__tests__"
    args.restoreCwd = False
    runCmd(args)


@cli.command("fuzz", "Fuzz a component")
def _(args: RunArgs):
    args.restoreCwd = False
    args.mixins.append("fuzz")
    args.component = args.component + ".fuzz"
    runCmd(args)


class InstallArgs(model.TargetArgs):
    component: str = cli.operand("component", "Component to build", default="__main__")

    prefix: str = cli.arg("p", "prefix", "Installation prefix", default="/usr/local")
    sysroot: str = cli.arg("s", "sysroot", "Installation sysroot", default="")
    format: str = cli.arg("f", "format", "Installation format", default="unix")


@cli.command("clean", "Clean build files")
def _():
    model.Project.use()
    shell.rmrf(const.BUILD_DIR)
