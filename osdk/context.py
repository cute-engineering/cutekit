from typing import cast, Protocol
from pathlib import Path


from osdk.model import TargetManifest, ComponentManifest, Props, Type, Tool, Tools
from osdk.logger import Logger
from osdk import const, shell, jexpr, utils, rules, mixins

logger = Logger("context")


class IContext(Protocol):
    def builddir(self) -> str:
        ...


class ComponentInstance:
    manifest: ComponentManifest
    sources: list[str] = []
    resolved: list[str] = []

    def __init__(
            self,
            manifest: ComponentManifest,
            sources: list[str],
            resolved: list[str]):
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
            map(lambda x: x.cinclude(), self.instances))
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


def loadTarget(id: str) -> TargetManifest:
    try:
        return next(filter(lambda t: t.id == id, loadAllTargets()))
    except StopIteration:
        raise Exception(f"Target '{id}' not found")


def loadAllComponents() -> list[ComponentManifest]:
    files = shell.find(const.SRC_DIR, ["manifest.json"])
    return list(
        map(
            lambda path: ComponentManifest(jexpr.evalRead(path), path),
            files))


def filterDisabled(components: list[ComponentManifest], target: TargetManifest) -> list[ComponentManifest]:
    return list(filter(lambda c: c.isEnabled(target), components))


def providerFor(what: str, components: list[ComponentManifest]) -> str | None:
    result: list[ComponentManifest] = list(
        filter(lambda c: c.id == what, components))

    if len(result) == 0:
        # Try to find a provider
        result = list(filter(lambda x: (what in x.provides), components))

    if len(result) == 0:
        logger.error(f"No provider for {what}")
        return None

    if len(result) > 1:
        logger.error(f"Multiple providers for {what}: {result}")
        return None

    return result[0].id


def resolveDeps(componentSpec: str, components: list[ComponentManifest], target: TargetManifest) -> tuple[bool,  list[str]]:
    mapping = dict(map(lambda c: (c.id, c), components))

    def resolveInner(what: str, stack: list[str] = []) -> tuple[bool,  list[str]]:
        result: list[str] = []
        what = target.route(what)
        resolved = providerFor(what, components)

        if resolved is None:
            return False,  []

        if resolved in stack:
            raise Exception(f"Dependency loop: {stack} -> {resolved}")

        stack.append(resolved)

        for req in mapping[resolved].requires:
            keep, reqs = resolveInner(req, stack)

            if not keep:
                stack.pop()
                logger.error(f"Dependency {req} not met for {resolved}")
                return False,  []

            result.extend(reqs)

        stack.pop()
        result.insert(0, resolved)

        return True, result

    enabled, resolved = resolveInner(componentSpec)

    return enabled, resolved


def instanciate(componentSpec: str, components: list[ComponentManifest], target: TargetManifest) -> ComponentInstance | None:
    manifest = next(filter(lambda c: c.id == componentSpec, components))
    sources = shell.find(
        manifest.dirname(), ["*.c", "*.cpp", "*.s", "*.asm"], recusive=False)
    enabled, resolved = resolveDeps(componentSpec, components, target)

    if not enabled:
        return None

    return ComponentInstance(manifest, sources, resolved[1:])


context: dict = {}


def contextFor(targetSpec: str, props: Props = {}) -> Context:
    if targetSpec in context:
        return context[targetSpec]

    logger.log(f"Loading context for {targetSpec}")

    targetEls = targetSpec.split(":")

    if targetEls[0] == "":
        targetEls[0] = "host-" + shell.uname().machine

    target = loadTarget(targetEls[0])
    target.props |= props

    components = loadAllComponents()
    components = filterDisabled(components, target)

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

    instances = cast(list[ComponentInstance], list(filter(lambda e: e != None, map(lambda c: instanciate(
        c.id, components, target), components))))

    context[targetSpec] = Context(
        target,
        instances,
        tools,
    )

    return context[targetSpec]
