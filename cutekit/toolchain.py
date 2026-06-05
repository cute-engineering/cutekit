import copy
import dataclasses as dt
import json
import os
import sys
import tarfile
from pathlib import Path
from typing import ClassVar, Optional
from urllib import request

from . import cli, const, model, shell, vt100


LLVM_REPO_RELEASES = "https://api.github.com/repos/llvm/llvm-project/releases"


@dt.dataclass(frozen=True)
class Toolchain:
    version: str
    family: ClassVar[str]

    @staticmethod
    def create(family: str, version: str) -> "Toolchain":
        if family == LlvmToolchain.family:
            if version == LlvmSystemToolchain.SYSTEM_VERSION:
                return LlvmSystemToolchain(version)
            return LlvmToolchain(version)
        raise RuntimeError(f"Unknown toolchain family '{family}'")

    @staticmethod
    def parse(spec: str) -> "Toolchain":
        if "-" not in spec:
            raise RuntimeError(f"Invalid toolchain '{spec}'")

        family, version = spec.split("-", 1)
        if not family or not version:
            raise RuntimeError(f"Invalid toolchain '{spec}'")

        return Toolchain.create(family, version)

    @staticmethod
    def _selectionFile(isGlobal: bool) -> str:
        return const.GLOBAL_TOOLCHAIN_FILE if isGlobal else const.LOCAL_TOOLCHAIN_FILE

    @staticmethod
    def _readSelection(isGlobal: bool) -> Optional["Toolchain"]:
        path = Toolchain._selectionFile(isGlobal)
        if not os.path.exists(path):
            return None

        with open(path, "r") as f:
            value = f.read().strip()

        if not value:
            return None

        return Toolchain.parse(value)

    @staticmethod
    def selected() -> Optional["Toolchain"]:
        local = Toolchain._readSelection(False)
        if local is not None:
            return local
        return Toolchain._readSelection(True)

    @staticmethod
    def current() -> tuple[Optional["Toolchain"], Optional[str]]:
        local = Toolchain._readSelection(False)
        if local is not None:
            return local, "local"

        globalToolchain = Toolchain._readSelection(True)
        if globalToolchain is not None:
            return globalToolchain, "global"

        return None, None

    @staticmethod
    def resolve(spec: Optional[str]) -> Optional["Toolchain"]:
        if spec:
            if "-" not in spec:
                selected = Toolchain.selected()
                if selected is not None:
                    return selected
                if selected is None:
                    raise RuntimeError(
                        f"No selected toolchain for family '{spec}'. Run 'ck toolchain local {spec}-<version>' or pass '--toolchain={spec}-<version>'"
                    )
            return Toolchain.parse(spec)
        return Toolchain.selected()

    @staticmethod
    def installed() -> list["Toolchain"]:
        root = Path(const.GLOBAL_TOOLCHAINS_DIR)
        if not root.exists():
            return []

        result: list[Toolchain] = []
        for child in root.iterdir():
            if not (child.is_dir() or child.is_symlink()):
                continue
            try:
                toolchain = Toolchain.parse(child.name)
            except RuntimeError:
                continue

            result.append(toolchain)

        return sorted(result, key=str)

    def __str__(self) -> str:
        return f"{self.family}-{self.version}"

    def dir(self) -> str:
        raise RuntimeError(f"Unknown toolchain family '{self.family}'")

    def bin(self, cmd: str) -> str:
        return os.path.join(self.dir(), "bin", cmd)

    def select(self, isGlobal: bool = False):
        path = Toolchain._selectionFile(isGlobal)
        shell.mkdir(os.path.dirname(path))
        with open(path, "w") as f:
            f.write(str(self) + "\n")

    @staticmethod
    def unset(isGlobal: bool = False):
        path = Toolchain._selectionFile(isGlobal)
        if os.path.exists(path):
            os.remove(path)

    def isInstalled(self) -> bool:
        raise RuntimeError(f"Unknown toolchain family '{self.family}'")

    def install(self) -> "Toolchain":
        raise RuntimeError(f"Unknown toolchain family '{self.family}'")

    def apply(self, target: model.Target, tools: model.Tools) -> None:
        raise RuntimeError(f"Unknown toolchain family '{self.family}'")


@dt.dataclass(frozen=True)
class LlvmToolchain(Toolchain):
    family: ClassVar[str] = "llvm"

    @staticmethod
    def _normalizeArch(machine: str) -> str:
        match machine:
            case "x86_64":
                return "Linux-X64"
            case "aarch64" | "arm64":
                return "Linux-ARM64"
            case _:
                raise RuntimeError(f"Unsupported architecture {machine}")

    @staticmethod
    def _release(version: str) -> dict:
        if version == "latest":
            data = _readJson(f"{LLVM_REPO_RELEASES}/latest")
        elif version.count(".") >= 2:
            data = _readJson(f"{LLVM_REPO_RELEASES}/tags/llvmorg-{version}")
        else:
            releases = _readJson(f"{LLVM_REPO_RELEASES}?per_page=100")
            if not isinstance(releases, list):
                raise RuntimeError("Unexpected releases response from GitHub")

            prefix = f"llvmorg-{version}."
            candidates: list[tuple[tuple[int, ...], dict]] = []
            for release in releases:
                if not isinstance(release, dict):
                    continue

                tag = release.get("tag_name")
                if not isinstance(tag, str):
                    continue

                if tag == f"llvmorg-{version}":
                    return release

                if not tag.startswith(prefix):
                    continue

                resolved = tag.removeprefix("llvmorg-")
                try:
                    parsed = tuple(int(part) for part in resolved.split("."))
                except ValueError:
                    continue

                candidates.append((parsed, release))

            if not candidates:
                raise RuntimeError(f"LLVM release '{version}' was not found")

            candidates.sort(key=lambda item: item[0])
            data = candidates[-1][1]

        if not isinstance(data, dict):
            raise RuntimeError("Unexpected release response from GitHub")

        return data

    @staticmethod
    def _pickAsset(release: dict, arch: str) -> tuple[str, str]:
        assets = release.get("assets")
        if not isinstance(assets, list):
            raise RuntimeError("LLVM release assets are missing")

        for asset in assets:
            if not isinstance(asset, dict):
                continue

            name = asset.get("name")
            url = asset.get("browser_download_url")
            if not isinstance(name, str) or not isinstance(url, str):
                continue

            if not name.startswith("LLVM-"):
                continue

            if arch not in name:
                continue

            if name.endswith(".sig") or name.endswith(".jsonl"):
                continue

            if not (name.endswith(".tar.xz") or name.endswith(".tar.zst")):
                continue

            return name, url

        raise RuntimeError(
            f"Toolchain version {release.get('tag_name', 'unknown')} not found for {arch}"
        )

    @staticmethod
    def _majorVersionFromClang(clang: str) -> str:
        versionLine = shell.popen(clang, "--version").splitlines()[0]
        version = versionLine.split()[2]
        return version.split(".")[0]

    def dir(self) -> str:
        return os.path.join(const.GLOBAL_TOOLCHAINS_DIR, str(self))

    def isInstalled(self) -> bool:
        clang = self.bin("clang")
        return os.path.exists(clang) and os.access(clang, os.X_OK)

    def install(self) -> Toolchain:
        release = LlvmToolchain._release(self.version)
        tag = release.get("tag_name")
        if not isinstance(tag, str) or not tag.startswith("llvmorg-"):
            raise RuntimeError("Unexpected LLVM release tag")

        normalized = tag.removeprefix("llvmorg-")
        toolchain = LlvmToolchain(normalized)
        if toolchain.isInstalled():
            return toolchain

        arch = LlvmToolchain._normalizeArch(shell.uname().machine)
        _, url = LlvmToolchain._pickAsset(release, arch)
        archive = _download(url)
        dest = toolchain.dir()

        if os.path.isdir(dest):
            shell.rmrf(dest)

        _extractTarball(archive, dest)
        toolchain._createLinks()
        toolchain._createAliases()
        return toolchain

    def _createLinks(self):
        binDir = os.path.join(self.dir(), "bin")
        major = LlvmToolchain._majorVersionFromClang(self.bin("clang"))

        for src, dest in [
            ("clang-scan-deps", f"clang-scan-deps-{major}"),
            ("clang++", f"clang++-{major}"),
            ("clang", f"clang-{major}"),
        ]:
            link = os.path.join(binDir, dest)
            if os.path.lexists(link):
                os.remove(link)
            os.symlink(src, link)

    def _createAliases(self):
        root = Path(const.GLOBAL_TOOLCHAINS_DIR)
        target = Path(str(self))
        parts = self.version.split(".")
        aliases: list[str] = []

        if len(parts) >= 1:
            aliases.append(str(LlvmToolchain(parts[0])))
        if len(parts) >= 2:
            aliases.append(str(LlvmToolchain(".".join(parts[:2]))))

        for alias in aliases:
            if alias == target.name:
                continue

            link = root / alias
            if link.exists() or link.is_symlink():
                if link.is_dir() and not link.is_symlink():
                    shell.rmrf(str(link))
                else:
                    link.unlink()
            os.symlink(target.name, link)

    def apply(self, target: model.Target, tools: model.Tools) -> None:
        clang = self.bin("clang")
        clangxx = self.bin("clang++")
        scan = self.bin("clang-scan-deps")

        if not os.path.exists(clang):
            raise RuntimeError(
                f"Toolchain '{self}' is not installed in {self.dir()}. Run 'ck toolchain install {self.family} --version={self.version}'"
            )

        target.props["toolchain"] = self.family
        tools.setdefault("cc", model.Tool())
        tools.setdefault("cxx", model.Tool())
        tools.setdefault("ld", model.Tool())
        tools.setdefault("ld-shared", model.Tool())
        tools.setdefault("cxx-scan", model.Tool())

        tools["cc"].cmd = shell.env('CC',  clang)
        tools["cxx"].cmd = shell.env('CXX', clangxx)
        tools["ld"].cmd = shell.env('LD', clangxx)
        tools["ld-shared"].cmd = shell.env('LD', clangxx)
        tools["cxx-scan"].cmd = shell.env('CXX_SCAN_DEPS', scan)


@dt.dataclass(frozen=True)
class LlvmSystemToolchain(LlvmToolchain):
    SYSTEM_VERSION: ClassVar[str] = "system"

    def dir(self) -> str:
        raise RuntimeError("llvm-system is provided by the system PATH")

    def bin(self, cmd: str) -> str:
        return shell.latest(cmd)

    def isInstalled(self) -> bool:
        return True

    def install(self) -> Toolchain:
        return self

    def apply(self, target: model.Target, tools: model.Tools) -> None:
        target.props["toolchain"] = self.family

def _readJson(url: str) -> object:
    with request.urlopen(url) as response:
        return json.load(response)


def _download(url: str) -> str:
    filename = os.path.basename(url)
    cached = os.path.join(const.GLOBAL_CACHE_DIR, filename)
    if os.path.exists(cached):
        print(f"Using cached archive {filename}", file=sys.stderr)
        return cached

    shell.mkdir(os.path.dirname(cached))

    lastShown = -1

    def onProgress(blocks: int, blockSize: int, totalSize: int):
        nonlocal lastShown

        current = blocks * blockSize
        if totalSize > 0:
            current = min(current, totalSize)
            percent = int((current * 100) / totalSize)
            if percent == lastShown and current != totalSize:
                return
            lastShown = percent

        vt100.printProgress(f"Downloading {filename}", current, totalSize)

    request.urlretrieve(url, cached, onProgress)
    archiveSize = os.path.getsize(cached)
    vt100.finishProgress(f"Downloading {filename}", archiveSize, archiveSize)
    return cached


def _extractTarball(archive: str, dest: str):
    shell.mkdir(dest)
    with tarfile.open(archive, "r:*") as tar:
        members = tar.getmembers()
        prefix = None
        for member in members:
            parts = Path(member.name).parts
            if not parts:
                continue
            if prefix is None:
                prefix = parts[0]
            elif parts[0] != prefix:
                prefix = None
                break

        def rewrite(member: tarfile.TarInfo) -> Optional[tarfile.TarInfo]:
            parts = Path(member.name).parts
            if prefix and len(parts) > 1 and parts[0] == prefix:
                member = copy.copy(member)
                member.name = str(Path(*parts[1:]))
                return member
            if prefix and len(parts) == 1 and parts[0] == prefix:
                return None
            return member

        rewritten = list(filter(None, (rewrite(member) for member in members)))
        total = len(rewritten)
        lastShown = -1

        for index, member in enumerate(rewritten, start=1):
            tar.extract(member, dest)

            if total == 0:
                continue

            percent = int((index * 100) / total)
            if percent == lastShown and index != total:
                continue

            lastShown = percent
            vt100.printProgress(f"Extracting {os.path.basename(archive)}", index, total)

        if total > 0:
            vt100.finishProgress(f"Extracting {os.path.basename(archive)}", total, total)

def apply(target: model.Target, tools: model.Tools):
    toolchain = Toolchain.resolve(target.props.get("toolchain"))
    if toolchain is None:
        return
    toolchain.apply(target, tools)


@cli.command("toolchain", "Manage toolchains")
def _():
    pass


class InstallArgs:
    name: str = cli.operand("name", "Toolchain family")
    version: str = cli.arg(None, "version", "Toolchain version", default="latest")


@cli.command("toolchain/install", "Install a toolchain")
def _(args: InstallArgs):
    toolchain = Toolchain.create(args.name, args.version).install()
    print(toolchain)


class SelectArgs:
    name: str = cli.operand("name", "Toolchain name")


class UnsetArgs:
    global_: bool = cli.arg(None, "global", "Unset the global toolchain")
    all: bool = cli.arg(None, "all", "Unset both local and global toolchains")


@cli.command("toolchain/local", "Select the local toolchain")
def _(args: SelectArgs):
    Toolchain.parse(args.name).select(isGlobal=False)


@cli.command("toolchain/global", "Select the global toolchain")
def _(args: SelectArgs):
    Toolchain.parse(args.name).select(isGlobal=True)


@cli.command("toolchain/unset", "Unset the selected toolchain")
def _(args: UnsetArgs):
    if args.all:
        Toolchain.unset(isGlobal=False)
        Toolchain.unset(isGlobal=True)
        return

    Toolchain.unset(isGlobal=args.global_)


@cli.command("toolchain/list", "List installed toolchains")
def _():
    currentToolchain, currentScope = Toolchain.current()
    for toolchain in Toolchain.installed():
        suffix = ""
        if toolchain == currentToolchain and currentScope is not None:
            suffix = f" ({currentScope})"
        print(str(toolchain) + suffix)


@cli.command("toolchain/current", "Show the current toolchain")
def _():
    toolchain, scope = Toolchain.current()
    if toolchain is None or scope is None:
        print("(none)")
        return

    print(f"{toolchain} ({scope})")
