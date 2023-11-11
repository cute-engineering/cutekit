from typing import cast, Optional, Protocol, Iterable
from itertools import chain
from pathlib import Path
import os
import logging

from cutekit.model import (
    Project,
    Target,
    Component,
    Props,
    Type,
    Tool,
    Tools,
)
from cutekit import const, shell, jexpr, utils, rules, mixins, project

_logger = logging.getLogger(__name__)


class IContext(Protocol):
    target: Target

    def builddir(self) -> str:
        ...


class ComponentInstance:
    enabled: bool = True
    disableReason = ""
    manifest: Component
    sources: list[str] = []
    res: list[str] = []
    resolved: list[str] = []
    context: IContext

    def __init__(
        self,
        enabled: bool,
        disableReason: str,
        manifest: Component,
        sources: list[str],
        res: list[str],
        resolved: list[str],
    ):
        self.enabled = enabled
        self.disableReason = disableReason
        self.manifest = manifest
        self.sources = sources
        self.res = res
        self.resolved = resolved

    def id(self) -> str:
        return self.manifest.id

    def isLib(self):
        return self.manifest.type == Type.LIB

    def objdir(self) -> str:
        return os.path.join(self.context.builddir(), f"{self.manifest.id}/obj")

    def resdir(self) -> str:
        return os.path.join(self.context.builddir(), f"{self.manifest.id}/res")

    def objsfiles(self) -> list[tuple[str, str]]:
        def toOFile(s: str) -> str:
            return os.path.join(
                self.objdir(),
                s.replace(os.path.join(self.manifest.dirname(), ""), "") + ".o",
            )

        return list(map(lambda s: (s, toOFile(s)), self.sources))

    def resfiles(self) -> list[tuple[str, str, str]]:
        def toAssetFile(s: str) -> str:
            return os.path.join(
                self.resdir(),
                s.replace(os.path.join(self.manifest.dirname(), "res/"), ""),
            )

        def toAssetId(s: str) -> str:
            return s.replace(os.path.join(self.manifest.dirname(), "res/"), "")

        return list(map(lambda s: (s, toAssetFile(s), toAssetId(s)), self.res))

    def outfile(self) -> str:
        if self.isLib():
            return os.path.join(
                self.context.builddir(), self.manifest.id, f"lib/{self.manifest.id}.a"
            )
        else:
            return os.path.join(
                self.context.builddir(), self.manifest.id, f"bin/{self.manifest.id}.out"
            )

    def cinclude(self) -> str:
        if "cpp-root-include" in self.manifest.props:
            return self.manifest.dirname()
        elif self.manifest.type == Type.LIB:
            return str(Path(self.manifest.dirname()).parent)
        else:
            return ""


class Context(IContext):
    target: Target
    instances: list[ComponentInstance]
    tools: Tools

    def enabledInstances(self) -> Iterable[ComponentInstance]:
        return filter(lambda x: x.enabled, self.instances)

    def __init__(
        self, target: Target, instances: list[ComponentInstance], tools: Tools
    ):
        self.target = target
        self.instances = instances
        self.tools = tools

    def componentByName(self, name: str) -> Optional[ComponentInstance]:
        result = list(filter(lambda x: x.manifest.id == name, self.instances))
        if len(result) == 0:
            return None
        return result[0]

    def cincls(self) -> list[str]:
        includes = list(
            filter(
                lambda x: x != "", map(lambda x: x.cinclude(), self.enabledInstances())
            )
        )
        return utils.uniq(includes)

    def cdefs(self) -> list[str]:
        return self.target.cdefs()

    def hashid(self) -> str:
        return utils.hash(
            (self.target.props, [self.tools[t].toJson() for t in self.tools])
        )[0:8]

    def builddir(self) -> str:
        return os.path.join(const.BUILD_DIR, f"{self.target.id}-{self.hashid()[:8]}")


def loadAllTargets() -> list[Target]:
    projectRoot = project.root()
    if projectRoot is None:
        return []

    pj = loadProject(projectRoot)
    paths = list(
        map(
            lambda e: os.path.join(const.EXTERN_DIR, e, const.TARGETS_DIR),
            pj.extern.keys(),
        )
    ) + [const.TARGETS_DIR]

    ret = []
    for entry in paths:
        files = shell.find(entry, ["*.json"])
        ret += list(map(lambda path: Target(jexpr.evalRead(path), path), files))

    return ret


def loadProject(path: str) -> Project:
    path = os.path.join(path, "project.json")
    return Project(jexpr.evalRead(path), path)


def loadTarget(id: str) -> Target:
    try:
        return next(filter(lambda t: t.id == id, loadAllTargets()))
    except StopIteration:
        raise RuntimeError(f"Target '{id}' not found")


def loadAllComponents() -> list[Component]:
    files = shell.find(const.SRC_DIR, ["manifest.json"])
    files += shell.find(const.EXTERN_DIR, ["manifest.json"])

    return list(map(lambda path: Component(jexpr.evalRead(path), path), files))


def filterDisabled(
    components: list[Component], target: Target
) -> tuple[list[Component], list[Component]]:
    return list(filter(lambda c: c.isEnabled(target)[0], components)), list(
        filter(lambda c: not c.isEnabled(target)[0], components)
    )


def providerFor(what: str, components: list[Component]) -> tuple[Optional[str], str]:
    result: list[Component] = list(filter(lambda c: c.id == what, components))

    if len(result) == 0:
        # Try to find a provider
        result = list(filter(lambda x: (what in x.provides), components))

    if len(result) == 0:
        _logger.error(f"No provider for '{what}'")
        return (None, f"No provider for '{what}'")

    if len(result) > 1:
        ids = list(map(lambda x: x.id, result))
        _logger.error(f"Multiple providers for '{what}': {result}")
        return (None, f"Multiple providers for '{what}': {','.join(ids)}")

    return (result[0].id, "")


def resolveDeps(
    componentSpec: str, components: list[Component], target: Target
) -> tuple[bool, str, list[str]]:
    mapping = dict(map(lambda c: (c.id, c), components))

    def resolveInner(what: str, stack: list[str] = []) -> tuple[bool, str, list[str]]:
        result: list[str] = []
        what = target.route(what)
        resolved, unresolvedReason = providerFor(what, components)

        if resolved is None:
            return False, unresolvedReason, []

        if resolved in stack:
            raise RuntimeError(f"Dependency loop: {stack} -> {resolved}")

        stack.append(resolved)

        for req in mapping[resolved].requires:
            keep, unresolvedReason, reqs = resolveInner(req, stack)

            if not keep:
                stack.pop()
                _logger.error(f"Dependency '{req}' not met for '{resolved}'")
                return False, unresolvedReason, []

            result.extend(reqs)

        stack.pop()
        result.insert(0, resolved)

        return True, "", result

    enabled, unresolvedReason, resolved = resolveInner(componentSpec)

    return enabled, unresolvedReason, resolved


def instanciate(
    componentSpec: str, components: list[Component], target: Target
) -> Optional[ComponentInstance]:
    manifest = next(filter(lambda c: c.id == componentSpec, components))
    wildcards = set(chain(*map(lambda rule: rule.fileIn, rules.rules.values())))
    sources = shell.find(manifest.subdirs, list(wildcards), recusive=False)

    res = shell.find(os.path.join(manifest.dirname(), "res"))

    enabled, unresolvedReason, resolved = resolveDeps(componentSpec, components, target)

    return ComponentInstance(
        enabled, unresolvedReason, manifest, sources, res, resolved[1:]
    )


def instanciateDisabled(component: Component, target: Target) -> ComponentInstance:
    return ComponentInstance(
        enabled=False,
        disableReason=component.isEnabled(target)[1],
        manifest=component,
        sources=[],
        res=[],
        resolved=[],
    )


context: dict[str, Context] = {}


def contextFor(targetSpec: str, props: Props = {}) -> Context:
    if targetSpec in context:
        return context[targetSpec]

    _logger.info(f"Loading context for '{targetSpec}'")

    targetEls = targetSpec.split(":")

    if targetEls[0] == "":
        targetEls[0] = "host-" + shell.uname().machine

    target = loadTarget(targetEls[0])
    target.props |= props

    components = loadAllComponents()
    components, disabled = filterDisabled(components, target)

    tools: Tools = {}

    for toolSpec in target.tools:
        tool = target.tools[toolSpec]

        tools[toolSpec] = Tool(
            strict=False, cmd=tool.cmd, args=tool.args, files=tool.files
        )

        tools[toolSpec].args += rules.rules[toolSpec].args

    for m in targetEls[1:]:
        mixin = mixins.byId(m)
        tools = mixin(target, tools)

    for component in components:
        for toolSpec in component.tools:
            tool = component.tools[toolSpec]
            tools[toolSpec].args += tool.args

    instances: list[ComponentInstance] = list(
        map(lambda c: instanciateDisabled(c, target), disabled)
    )

    instances += cast(
        list[ComponentInstance],
        list(
            filter(
                lambda e: e is not None,
                map(lambda c: instanciate(c.id, components, target), components),
            )
        ),
    )

    context[targetSpec] = Context(
        target,
        instances,
        tools,
    )

    for instance in instances:
        instance.context = context[targetSpec]

    return context[targetSpec]
