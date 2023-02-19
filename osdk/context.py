from typing import cast, Protocol, Iterable
from itertools import chain
from pathlib import Path
import os


from osdk.model import ProjectManifest, TargetManifest, ComponentManifest, Props, Type, Tool, Tools
from osdk.logger import Logger
from osdk import const, shell, jexpr, utils, rules, mixins

logger = Logger("context")


class IContext(Protocol):
    def builddir(self) -> str:
        ...


class ComponentInstance:
    enabled: bool = True
    disableReason = ""
    manifest: ComponentManifest
    sources: list[str] = []
    resolved: list[str] = []

    def __init__(
            self,
            enabled: bool,
            disableReason: str,
            manifest: ComponentManifest,
            sources: list[str],
            resolved: list[str]):
        self.enabled = enabled
        self.disableReason = disableReason
        self.manifest = manifest
        self.sources = sources
        self.resolved = resolved

    def isLib(self):
        return self.manifest.type == Type.LIB

    def binfile(self, context: IContext) -> str:
        return f"{context.builddir()}/bin/{self.manifest.id}.out"

    def objdir(self, context: IContext) -> str:
        return f"{context.builddir()}/obj/{self.manifest.id}"

    def objsfiles(self, context: IContext) -> list[tuple[str, str]]:
        return list(
            map(
                lambda s: (
                    s, f"{self.objdir(context)}/{s.replace(self.manifest.dirname() + '/', '')}.o"),
                self.sources))

    def libfile(self, context: IContext) -> str:
        return f"{context.builddir()}/lib/{self.manifest.id}.a"

    def outfile(self, context: IContext) -> str:
        if self.isLib():
            return self.libfile(context)
        else:
            return self.binfile(context)

    def cinclude(self) -> str:
        if "cpp-root-include" in self.manifest.props:
            return self.manifest.dirname()
        else:
            return str(Path(self.manifest.dirname()).parent)


class Context(IContext):
    target: TargetManifest
    instances: list[ComponentInstance]
    tools: Tools

    def enabledInstances(self) -> Iterable[ComponentInstance]:
        return filter(lambda x: x.enabled, self.instances)

    def __init__(self, target: TargetManifest, instances: list[ComponentInstance], tools: Tools):
        self.target = target
        self.instances = instances
        self.tools = tools

    def componentByName(self, name: str) -> ComponentInstance | None:
        result = list(filter(lambda x: x.manifest.id == name, self.instances))
        if len(result) == 0:
            return None
        return result[0]

    def cincls(self) -> list[str]:
        includes = list(
            map(lambda x: x.cinclude(), self.enabledInstances()))
        return utils.uniq(includes)

    def cdefs(self) -> list[str]:
        return self.target.cdefs()

    def hashid(self) -> str:
        return utils.hash((self.target.props, str(self.tools)))[0:8]

    def builddir(self) -> str:
        return f"{const.BUILD_DIR}/{self.target.id}-{self.hashid()[:8]}"


def loadAllTargets() -> list[TargetManifest]:
    files = shell.find(const.TARGETS_DIR, ["*.json"])
    return list(
        map(lambda path: TargetManifest(jexpr.evalRead(path), path), files))


def loadProject(path: str) -> ProjectManifest:
    path = os.path.join(path, "project.json")
    return ProjectManifest(jexpr.evalRead(path), path)


def loadTarget(id: str) -> TargetManifest:
    try:
        return next(filter(lambda t: t.id == id, loadAllTargets()))
    except StopIteration:
        raise Exception(f"Target '{id}' not found")


def loadAllComponents() -> list[ComponentManifest]:
    files = shell.find(const.SRC_DIR, ["manifest.json"])
    files += shell.find(const.EXTERN_DIR, ["manifest.json"])

    return list(
        map(
            lambda path: ComponentManifest(jexpr.evalRead(path), path),
            files))


def filterDisabled(components: list[ComponentManifest], target: TargetManifest) -> tuple[list[ComponentManifest], list[ComponentManifest]]:
    return list(filter(lambda c: c.isEnabled(target)[0], components)), \
        list(filter(lambda c: not c.isEnabled(target)[0], components))


def providerFor(what: str, components: list[ComponentManifest]) -> tuple[str | None, str]:
    result: list[ComponentManifest] = list(
        filter(lambda c: c.id == what, components))

    if len(result) == 0:
        # Try to find a provider
        result = list(filter(lambda x: (what in x.provides), components))

    if len(result) == 0:
        logger.error(f"No provider for '{what}'")
        return (None, f"No provider for '{what}'")

    if len(result) > 1:
        ids = list(map(lambda x: x.id, result))
        logger.error(f"Multiple providers for '{what}': {result}")
        return (None, f"Multiple providers for '{what}': {','.join(ids)}")

    return (result[0].id, "")


def resolveDeps(componentSpec: str, components: list[ComponentManifest], target: TargetManifest) -> tuple[bool, str,  list[str]]:
    mapping = dict(map(lambda c: (c.id, c), components))

    def resolveInner(what: str, stack: list[str] = []) -> tuple[bool, str,  list[str]]:
        result: list[str] = []
        what = target.route(what)
        resolved, unresolvedReason = providerFor(what, components)

        if resolved is None:
            return False, unresolvedReason,  []

        if resolved in stack:
            raise Exception(f"Dependency loop: {stack} -> {resolved}")

        stack.append(resolved)

        for req in mapping[resolved].requires:
            keep, unresolvedReason,  reqs = resolveInner(req, stack)

            if not keep:
                stack.pop()
                logger.error(f"Dependency '{req}' not met for '{resolved}'")
                return False, unresolvedReason,  []

            result.extend(reqs)

        stack.pop()
        result.insert(0, resolved)

        return True, "", result

    enabled, unresolvedReason, resolved = resolveInner(componentSpec)

    return enabled, unresolvedReason, resolved


def instanciate(componentSpec: str, components: list[ComponentManifest], target: TargetManifest) -> ComponentInstance | None:
    manifest = next(filter(lambda c: c.id == componentSpec, components))
    wildcards = set(chain(*map(lambda rule: rule.fileIn, rules.rules.values())))
    sources = shell.find(
        manifest.dirname(), list(wildcards), recusive=False)
    enabled, unresolvedReason, resolved = resolveDeps(
        componentSpec, components, target)

    return ComponentInstance(enabled, unresolvedReason, manifest, sources, resolved[1:])


def instanciateDisabled(component: ComponentManifest,  target: TargetManifest) -> ComponentInstance:
    return ComponentInstance(False, component.isEnabled(target)[1], component, [], [])


context: dict = {}


def contextFor(targetSpec: str, props: Props = {}) -> Context:
    if targetSpec in context:
        return context[targetSpec]

    logger.log(f"Loading context for '{targetSpec}'")

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
            strict=False,
            cmd=tool.cmd,
            args=tool.args,
            files=tool.files)

        tools[toolSpec].args += rules.rules[toolSpec].args

    for m in targetEls[1:]:
        mixin = mixins.byId(m)
        tools = mixin(target, tools)

    for component in components:
        for toolSpec in component.tools:
            tool = component.tools[toolSpec]
            tools[toolSpec].args += tool.args

    instances: list[ComponentInstance] = list(
        map(lambda c: instanciateDisabled(c, target), disabled))

    instances += cast(list[ComponentInstance], list(filter(lambda e: e != None, map(lambda c: instanciate(
        c.id, components, target), components))))

    context[targetSpec] = Context(
        target,
        instances,
        tools,
    )

    return context[targetSpec]
