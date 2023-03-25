from typing import Callable
from osdk.model import TargetManifest, Tools

Mixin = Callable[[TargetManifest, Tools], Tools]


def patchToolArgs(tools: Tools, toolSpec: str, args: list[str]):
    tools[toolSpec].args += args


def prefixToolCmd(tools: Tools, toolSpec: str, prefix: str):
    tools[toolSpec].cmd = prefix + " " + tools[toolSpec].cmd


def mixinCache(target: TargetManifest, tools: Tools) -> Tools:
    prefixToolCmd(tools, "cc", "ccache")
    prefixToolCmd(tools, "cxx", "ccache")
    return tools


def makeMixinSan(san: str) -> Mixin:
    def mixinSan(target: TargetManifest, tools: Tools) -> Tools:
        patchToolArgs(
            tools, "cc", [f"-fsanitize={san}"])
        patchToolArgs(
            tools, "cxx", [f"-fsanitize={san}"])
        patchToolArgs(
            tools, "ld", [f"-fsanitize={san}"])

        return tools

    return mixinSan


def makeMixinOptimize(level: str) -> Mixin:
    def mixinOptimize(target: TargetManifest, tools: Tools) -> Tools:
        patchToolArgs(tools, "cc", [f"-O{level}"])
        patchToolArgs(tools, "cxx", [f"-O{level}"])

        return tools

    return mixinOptimize


def mixinDebug(target: TargetManifest, tools: Tools) -> Tools:
    patchToolArgs(tools, "cc", ["-g", "-gdwarf-4"])
    patchToolArgs(tools, "cxx", ["-g", "-gdwarf-4"])

    return tools


mixins: dict[str, Mixin] = {
    "cache": mixinCache,
    "debug": mixinDebug,
    "asan": makeMixinSan("address"),
    "msan": makeMixinSan("memory"),
    "tsan": makeMixinSan("thread"),
    "ubsan": makeMixinSan("undefined"),
    "o3": makeMixinOptimize("3"),
    "o2": makeMixinOptimize("2"),
    "o1": makeMixinOptimize("1"),
    "o0": makeMixinOptimize("0"),
}


def append(mixinSpec: str, mixin: Mixin):
    mixins[mixinSpec] = mixin


def byId(id: str) -> Mixin:
    return mixins[id]
