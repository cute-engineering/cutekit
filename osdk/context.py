from typing import cast
from pathlib import Path


from osdk.model import TargetManifest, ComponentManifest, Props, Type
from osdk.logger import Logger
from osdk import const, shell, jexpr, utils

logger = Logger("context")


class ComponentInstance:
    target: TargetManifest
    manifest: ComponentManifest
    sources: list[str] = []
    resolved: list[str] = []

    def __init__(
            self,
            target: TargetManifest,
            manifest: ComponentManifest,
            sources: list[str],
            resolved: list[str]):
        self.target = target
        self.manifest = manifest
        self.sources = sources
        self.resolved = resolved

    def isLib(self):
        return self.manifest.type == Type.LIB

    def binfile(self) -> str:
        return f"{self.target.builddir()}/bin/{self.manifest.id}.out"

    def objdir(self) -> str:
        return f"{self.target.builddir()}/obj/{self.manifest.id}"

    def objsfiles(self) -> list[tuple[str, str]]:
        return list(
            map(
                lambda s: (
                    s, f"{self.objdir()}/{s.replace(self.manifest.dirname() + '/', '')}.o"),
                self.sources))

    def libfile(self) -> str:
        return f"{self.target.builddir()}/lib/{self.manifest.id}.a"

    def outfile(self) -> str:
        if self.isLib():
            return self.libfile()
        return self.binfile()

    def cinclude(self) -> str:
        if "cpp-root-include" in self.manifest.props:
            return self.manifest.dirname()
        else:
            return str(Path(self.manifest.dirname()).parent)


class Context:
    target: TargetManifest
    instances: list[ComponentInstance] = []

    def __init__(self, target: TargetManifest, instances: list[ComponentInstance]):
        self.target = target
        self.instances = instances

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

    def builddir(self) -> str:
        return self.target.builddir()


def loadAllTargets() -> list[TargetManifest]:
    files = shell.find(const.TARGETS_DIR, ["*.json"])
    return list(
        map(lambda path: TargetManifest(jexpr.evalRead(path), path), files))


def loadTarget(id: str) -> TargetManifest:
    return next(filter(lambda t: t.id == id, loadAllTargets()))


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
        result.append(resolved)

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

    return ComponentInstance(target, manifest, sources, resolved[:-1])


def contextFor(targetSpec: str, props: Props) -> Context:
    logger.log(f"Loading context for {targetSpec}")

    target = loadTarget(targetSpec)
    components = loadAllComponents()

    components = filterDisabled(components, target)
    instances = cast(list[ComponentInstance], list(filter(lambda e: e != None, map(lambda c: instanciate(
        c.id, components, target), components))))

    return Context(
        target,
        instances
    )
