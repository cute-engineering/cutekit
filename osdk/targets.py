
import copy
import os

from . import utils


def patchToolArgs(target, tool, args):
    target = copy.deepcopy(target)

    target["tools"][tool]["args"] += args

    return target


def prefixToolCmd(target, tool, prefix):
    target = copy.deepcopy(target)

    target["tools"][tool]["cmd"] = prefix + " " + target["tools"][tool]["cmd"]

    return target


def enableCache(target: dict) -> dict:
    target = copy.deepcopy(target)

    target = prefixToolCmd(target, "cc", f"ccache")
    target = prefixToolCmd(target, "cxx", f"ccache")

    return target


def enableSan(target: dict) -> dict:
    if (target["freestanding"]):
        return target

    target = copy.deepcopy(target)

    target = patchToolArgs(
        target, "cc", ["-fsanitize=address", "-fsanitize=undefined"])
    target = patchToolArgs(
        target, "cxx", ["-fsanitize=address", "-fsanitize=undefined"])
    target = patchToolArgs(
        target, "ld", ["-fsanitize=address", "-fsanitize=undefined"])

    return target


def enableColors(target: dict) -> dict:
    target = copy.deepcopy(target)

    if (target["props"]["toolchain"] == "clang"):
        target = patchToolArgs(target, "cc", ["-fcolor-diagnostics"])
        target = patchToolArgs(target, "cxx", ["-fcolor-diagnostics"])
    elif (target["props"]["toolchain"] == "gcc"):
        target = patchToolArgs(target, "cc", ["-fdiagnostics-color=alaways"])
        target = patchToolArgs(target, "cxx", ["-fdiagnostics-color=alaways"])

    return target


def enableOptimizer(target: dict, level: str) -> dict:
    target = copy.deepcopy(target)

    target = patchToolArgs(target, "cc", ["-O" + level])
    target = patchToolArgs(target, "cxx", ["-O" + level])

    return target


def available() -> list:
    return [file.removesuffix(".json") for file in utils.tryListDir("meta/targets")
            if file.endswith(".json")]


VARIANTS = ["debug", "devel", "release", "sanitize"]


def load(targetId: str, props: dict) -> dict:
    targetName = targetId
    targetVariant = "devel"
    if ":" in targetName:
        targetName, targetVariant = targetName.split(":")

    if not targetName in available():
        raise utils.CliException(f"Target '{targetName}' not available")

    if not targetVariant in VARIANTS:
        raise utils.CliException(f"Variant '{targetVariant}' not available")

    target = utils.loadJson(f"meta/targets/{targetName}.json")
    target["props"]["variant"] = targetVariant
    target["props"] = {**target["props"], **props}

    defines = []

    for key in target["props"]:
        macroname = key.lower().replace("-", "_")
        prop = target["props"][key]
        macrovalue = str(prop).lower().replace(" ", "_").replace("-", "_")
        if isinstance(prop, bool):
            if prop:
                defines += [f"-D__osdk_{macroname}__"]
        else:
            defines += [f"-D__osdk_{macroname}_{macrovalue}__"]

    target = patchToolArgs(target, "cc", [
        "-std=gnu2x",
        "-Isrc",
        "-Wall",
        "-Wextra",
        "-Werror",
        *defines
    ])

    target = patchToolArgs(target, "cxx", [
        "-std=gnu++2b",
        "-Isrc",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-fno-exceptions",
        "-fno-rtti",
        *defines
    ])

    target["hash"] = utils.objSha256(target, ["props", "tools"])
    target["key"] = utils.objKey(target["props"])
    target["dir"] = f".osdk/build/{target['hash'][:8]}"
    target["bindir"] = f"{target['dir']}/bin"
    target["objdir"] = f"{target['dir']}/obj"
    target["ninjafile"] = target["dir"] + "/build.ninja"

    target = enableColors(target)

    if targetVariant == "debug":
        target = enableOptimizer(target, "g")
    elif targetVariant == "devel":
        target = enableOptimizer(target, "2")
    elif targetVariant == "release":
        target = enableOptimizer(target, "3")
    elif targetVariant == "sanatize":
        target = enableOptimizer(target, "g")
        target = enableSan(target)

    return target
