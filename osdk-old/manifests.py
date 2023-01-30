import os
import copy
from pathlib import Path
from . import utils


def loadJsons(basedirs: list[str]) -> dict:
    result = {}
    for basedir in basedirs:
        for root, dirs, files in os.walk(basedir):
            for filename in files:
                if filename == 'manifest.json':
                    filename = os.path.join(root, filename)
                    manifest = utils.loadJson(filename)
                    result[manifest["id"]] = manifest

    return result


def filter(manifests: dict, target: dict) -> dict:
    manifests = copy.deepcopy(manifests)
    for id in manifests:
        manifest = manifests[id]
        accepted = True

        if "requires" in manifest:
            for req in manifest["requires"]:
                if not req in target["props"] or \
                   not target["props"][req] in manifest["requires"][req]:
                    accepted = False
                    print(
                        f"Disabling {id} because it requires {req}: {manifest['requires'][req]}")
                    break

        manifest["enabled"] = accepted

    return manifests


def doInjects(manifests: dict) -> dict:
    manifests = copy.deepcopy(manifests)
    for key in manifests:
        item = manifests[key]
        if item["enabled"] and "inject" in item:
            for inject in item["inject"]:
                if inject in manifests:
                    manifests[inject]["deps"].append(key)
    return manifests


def providersFor(key: str, manifests: dict) -> dict:
    result = []
    for k in manifests:
        if manifests[k]["enabled"] and key in manifests[k].get("provide", []):
            result.append(k)
    return result


def resolveDeps(manifests: dict) -> dict:
    manifests = copy.deepcopy(manifests)

    def resolve(key: str, stack: list[str] = []) -> list[str]:
        result: list[str] = []

        if not key in manifests:
            providers = providersFor(key, manifests)

            if len(providers) == 0:
                print("No providers for " + key)
                return False, "", []

            if len(providers) > 1:
                raise utils.CliException(
                    f"Multiple providers for {key}: {providers}")

            key = providers[0]

        if key in stack:
            raise utils.CliException("Circular dependency detected: " +
                                     str(stack) + " -> " + key)

        stack.append(key)

        if "deps" in manifests[key]:
            for dep in manifests[key]["deps"]:
                keep, dep, res = resolve(dep, stack)
                if not keep:
                    stack.pop()
                    print(f"Disabling {key} because we are missing a deps")
                    return False, "", []
                result.append(dep)
                result += res

        stack.pop()
        return True, key, result

    for key in manifests:
        keep, _, deps = resolve(key)
        if not keep:
            print(f"Disabling {key} because we are missing a deps")
            manifests[key]["enabled"] = False

        manifests[key]["deps"] = utils.stripDups(deps)

    return manifests


def findFiles(manifests: dict) -> dict:
    manifests = copy.deepcopy(manifests)

    for key in manifests:
        item = manifests[key]
        path = manifests[key]["dir"]
        testsPath = os.path.join(path, "tests")
        assetsPath = os.path.join(path, "assets")

        item["tests"] = utils.findFiles(testsPath, [".c", ".cpp"])
        item["srcs"] = utils.findFiles(path, [".c", ".cpp", ".s", ".asm"])
        item["assets"] = utils.findFiles(assetsPath)

    return manifests


def prepareTests(manifests: dict) -> dict:
    if not "tests" in manifests:
        return manifests
    manifests = copy.deepcopy(manifests)
    tests = manifests["tests"]

    for key in manifests:
        item = manifests[key]
        if "tests" in item and len(item["tests"]) > 0:
            tests["deps"] += [item["id"]]
            tests["srcs"] += item["tests"]

    return manifests


def prepareInOut(manifests: dict, target: dict) -> dict:
    manifests = copy.deepcopy(manifests)
    for key in manifests:
        item = manifests[key]
        basedir = os.path.dirname(item["dir"])

        item["objs"] = [(x.replace(basedir, target["objdir"]) + ".o", x)
                        for x in item["srcs"]]

        if item["type"] == "lib":
            item["out"] = target["bindir"] + "/" + key + ".a"
        elif item["type"] == "exe":
            item["out"] = target["bindir"] + "/" + key
        else:
            raise utils.CliException("Unknown type: " + item["type"])

    for key in manifests:
        item = manifests[key]
        item["libs"] = [manifests[x]["out"]
                        for x in item["deps"] if manifests[x]["type"] == "lib"]
    return manifests


def cincludes(manifests: dict) -> str:
    include_paths = []

    for key in manifests:
        item = manifests[key]
        if item["enabled"]:
            if "root-include" in item:
                include_paths.append(item["dir"])
            else:
                include_paths.append(str(Path(item["dir"]).parent))

    if len(include_paths) == 0:
        return ""

    # remove duplicates
    include_paths = utils.stripDups(include_paths)

    return " -I" + " -I".join(include_paths)


def loadAll(basedirs: list[str], target: dict) -> dict:
    manifests = loadJsons(basedirs)
    manifests = filter(manifests, target)
    manifests = doInjects(manifests)
    manifests = resolveDeps(manifests)
    manifests = findFiles(manifests)
    manifests = prepareTests(manifests)
    manifests = prepareInOut(manifests, target)

    return manifests
