from typing import TextIO, Tuple
import json
import copy
import os

from . import ninja
from . import manifests as m
from . import targets
from . import utils


def mergeToolsArgs(tool, layers):
    args = []
    for layer in layers:
        if not layer.get("enabled", True):
            continue

        args.extend(layer
                    .get("tools", {})
                    .get(tool, {})
                    .get("args", []))
    return args


def genNinja(out: TextIO, manifests: dict, target: dict) -> None:
    target = copy.deepcopy(target)
    target = targets.patchToolArgs(target, "cc", [m.cinc(manifests)])
    target = targets.patchToolArgs(target, "cxx", [m.cinc(manifests)])

    writer = ninja.Writer(out)

    writer.comment("File generated by the build system, do not edit")
    writer.newline()

    writer.comment("Tools:")
    for key in target["tools"]:
        tool = target["tools"][key]
        writer.variable(key, tool["cmd"])
        writer.variable(
            key + "flags", " ".join(mergeToolsArgs(key, [target] + list(manifests.values()))))
        writer.newline()

    writer.newline()

    writer.comment("Rules:")
    writer.rule(
        "cc", "$cc -c -o $out $in -MD -MF $out.d $ccflags",
        depfile="$out.d")

    writer.rule(
        "cxx", "$cxx -c -o $out $in -MD -MF $out.d $cxxflags",
        depfile="$out.d")

    writer.rule("ld", "$ld -o $out $in $ldflags")

    writer.rule("ar", "$ar crs $out $in")

    writer.rule("as", "$as -o $out $in $asflags")

    writer.newline()

    writer.comment("Build:")
    all = []
    for key in manifests:
        item = manifests[key]

        if not item["enabled"]:
            continue

        writer.comment("Project: " + item["id"])

        for obj in item["objs"]:
            if obj[1].endswith(".c"):
                writer.build(
                    obj[0], "cc", obj[1], order_only=target["tools"]["cc"].get("files", ""))
            elif obj[1].endswith(".cpp"):
                writer.build(
                    obj[0], "cxx", obj[1], order_only=target["tools"]["cxx"].get("files", ""))
            elif obj[1].endswith(".s") or obj[1].endswith(".asm"):
                writer.build(
                    obj[0], "as", obj[1], order_only=target["tools"]["as"].get("files", ""))

        writer.newline()

        objs = [x[0] for x in item["objs"]]

        if item["type"] == "lib":
            writer.build(item["out"], "ar", objs,
                         order_only=target["tools"]["ar"].get("files", ""))
        else:
            objs = objs + item["libs"]
            writer.build(item["out"], "ld", objs,
                         order_only=target["tools"]["ld"].get("files", ""))

        all.append(item["out"])

        writer.newline()

    writer.comment("Phony:")
    writer.build("all", "phony", all)


def prepare(targetId: str, props: dict) -> Tuple[dict, dict]:
    target = targets.load(targetId, props)

    includes = ["src"]

    if os.path.exists("osdk.json"):
        with open("osdk.json", "r") as f:
            osdk = json.load(f)
            includes = osdk["includes"]
            print("includes: ", includes)

    manifests = m.loadAll(includes, target)

    utils.mkdirP(target["dir"])
    genNinja(open(target["ninjafile"], "w"), manifests, target)

    meta = {}
    meta["id"] = target["key"]
    meta["type"] = "artifacts"
    meta["components"] = manifests
    meta["target"] = target

    with open(target["dir"] + "/manifest.json", "w") as f:
        json.dump(meta, f, indent=4)

    with open(target["dir"] + "/_key",  "w") as f:
        json.dump(target["key"], f, indent=4)

    return target, manifests


def buildAll(targetId: str, props: dict = {}) -> None:
    target, _ = prepare(targetId, props)
    print(f"{utils.Colors.BOLD}Building all components for target '{targetId}{utils.Colors.RESET}'")

    try:
        utils.runCmd("ninja", "-v",  "-f",  target["ninjafile"])
    except Exception as e:
        raise utils.CliException(
            "Failed to build all for " + target["key"] + ": " + e)


def buildOne(targetId: str, componentId: str, props: dict = {}) -> str:
    print(f"{utils.Colors.BOLD}Building {componentId} for target '{targetId}'{utils.Colors.RESET}")

    target, manifests = prepare(targetId, props)

    if not componentId in manifests:
        raise utils.CliException("Unknown component: " + componentId)

    if not manifests[componentId]["enabled"]:
        raise utils.CliException(
            f"{componentId} is not enabled for the {targetId} target")

    try:
        utils.runCmd("ninja", "-v", "-f",
                     target["ninjafile"], manifests[componentId]["out"])
    except Exception as e:
        raise utils.CliException(
            f"Failed to build {componentId} for target '{target['key']}': {e}")
    return manifests[componentId]["out"]