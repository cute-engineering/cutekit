import os
import sys
import hashlib
import errno
import subprocess
import signal
import re
import shutil
import fnmatch
import platform
import logging
import tempfile
import dataclasses as dt

from pathlib import Path
from typing import Optional
from . import cli, const, jexpr

_logger = logging.getLogger(__name__)


class ShellException(RuntimeError):
    def __init__(self, message: str, code: int):
        super().__init__(message)
        self.code = code


@dt.dataclass
class Uname:
    sysname: str
    distrib: str
    nodename: str
    release: str
    version: str
    machine: str


@jexpr.exposed("shell.uname")
def uname() -> Uname:
    un = platform.uname()

    if un.system == "Linux" and hasattr(platform, "freedesktop_os_release"):
        distrib = platform.freedesktop_os_release()
    else:
        distrib = {"NAME": "Unknown"}

    result = Uname(
        un.system.lower(),
        distrib["NAME"],
        un.node,
        un.release,
        un.version,
        un.machine,
    )

    match result.machine:
        case "aarch64":
            result.machine = "arm64"
        case "AMD64":
            result.machine = "x86_64"
        case _:
            pass

    _logger.debug(f"uname: {result}")

    return result


def sha256sum(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def find(
    path: str | list[str], wildcards: list[str] = [], recusive: bool = True
) -> list[str]:
    _logger.debug(f"Looking for files in {path} matching {wildcards}")

    result: list[str] = []

    if isinstance(wildcards, str):
        wildcards = [wildcards]

    if isinstance(path, list):
        for p in path:
            result += find(p, wildcards, recusive)
        return sorted(result)

    if not os.path.isdir(path):
        return []

    if recusive:
        for root, _, files in os.walk(path):
            for f in files:
                if len(wildcards) == 0:
                    result.append(os.path.join(root, f))
                else:
                    for wildcard in wildcards:
                        if fnmatch.fnmatch(f, wildcard):
                            result.append(os.path.join(root, f))
                            break
    else:
        for f in os.listdir(path):
            if len(wildcards) == 0:
                result.append(os.path.join(path, f))
            else:
                for wildcard in wildcards:
                    if fnmatch.fnmatch(f, wildcard):
                        result.append(os.path.join(path, f))
                        break

    # sort for reproducibility
    return sorted(result)


def either(paths: list[str]) -> str | None:
    for p in paths:
        if os.path.exists(p):
            return p
    return None


def mkdir(path: str) -> str:
    _logger.debug(f"Creating directory {path}")

    try:
        os.makedirs(path)
    except OSError as exc:
        if not (exc.errno == errno.EEXIST and os.path.isdir(path)):
            raise
    return path


def rmrf(path: str) -> bool:
    _logger.debug(f"Removing directory {path}")

    if not os.path.exists(path):
        return False
    if os.path.isfile(path):
        os.remove(path)
    else:
        shutil.rmtree(path, ignore_errors=True)
    return True


def wget(url: str, path: Optional[str] = None) -> str:
    import requests

    if path is None:
        path = os.path.join(
            const.CACHE_DIR, hashlib.sha256(url.encode("utf-8")).hexdigest()
        )

    if os.path.exists(path):
        _logger.debug(f"Using cached {path} for {url}")
        return path

    _logger.debug(f"Downloading {url} to {path}")

    r = requests.get(url, stream=True)
    r.raise_for_status()
    mkdir(os.path.dirname(path))
    with open(path, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)

    return path


def exec(*args: str, quiet: bool = False, cwd: Optional[str] = None) -> bool:
    _logger.debug(f"Executing {args}")
    cmdName = Path(args[0]).name

    try:
        proc = subprocess.run(
            args,
            cwd=cwd,
            stdout=sys.stdout if not quiet else subprocess.PIPE,
            stderr=sys.stderr if not quiet else subprocess.PIPE,
        )

        if proc.stdout:
            _logger.debug(proc.stdout.decode("utf-8"))

        if proc.stderr:
            _logger.debug(proc.stderr.decode("utf-8"))

    except FileNotFoundError:
        if cwd and not os.path.exists(cwd):
            raise RuntimeError(f"{cwd}: No such file or directory")
        else:
            raise RuntimeError(f"{args[0]}: Command not found")

    except KeyboardInterrupt:
        raise RuntimeError(f"{cmdName}: Interrupted")

    if proc.returncode == -signal.SIGSEGV:
        raise ShellException(f"{cmdName}: Segmentation fault", -signal.SIGSEGV)

    if proc.returncode != 0:
        raise ShellException(
            f"{cmdName}: Process exited with code {proc.returncode}", proc.returncode
        )

    return True


def popen(*args: str) -> str:
    _logger.debug(f"Executing {args}...")

    cmdName = Path(args[0]).name

    try:
        proc = subprocess.run(args, stdout=subprocess.PIPE, stderr=sys.stderr)
    except FileNotFoundError:
        raise RuntimeError(f"{cmdName}: Command not found")

    if proc.returncode == -signal.SIGSEGV:
        raise ShellException(f"{cmdName}: Segmentation fault", -signal.SIGSEGV)

    if proc.returncode != 0:
        raise ShellException(
            f"{cmdName}: Process exited with code {proc.returncode}", proc.returncode
        )

    return proc.stdout.decode("utf-8").strip()


@jexpr.exposed("shell.popen")
def _(*args: str) -> list[str]:
    return popen(*args).splitlines()


def debug(cmd: list[str], debugger: str = "lldb", wait: bool = False):
    if debugger == "lldb":
        exec(
            "lldb",
            *(("-o", "b main") if wait else ()),
            *("-o", "run"),
            *cmd,
        )
    elif debugger == "gdb":
        exec(
            "gdb",
            *(("-ex", "b main") if wait else ()),
            *("-ex", "run"),
            "--args",
            *cmd,
        )
    else:
        raise RuntimeError(f"Unknown debugger {debugger}")


def _profileCpuLinux(cmd: list[str], rate=1000):
    mkdir(const.TMP_DIR)
    perfFile = f"{const.TMP_DIR}/cpu-profile.data"
    try:
        exec(
            "perf",
            "record",
            "-F",
            str(rate),
            "-g",
            "-o",
            perfFile,
            "--call-graph",
            "dwarf",
            *cmd,
        )
    except Exception as e:
        if not os.path.exists(perfFile):
            raise e

    try:
        proc = subprocess.Popen(
            ["perf", "script", "-i", perfFile], stdout=subprocess.PIPE
        )
        subprocess.run(["speedscope", "-"], stdin=proc.stdout)
        proc.wait()
    except Exception as e:
        rmrf(perfFile)
        raise e

    rmrf(perfFile)


def _profileCpuDarwin(cmd: list[str], rate=1000):
    mkdir(const.TMP_DIR)
    traceFile = f"{const.TMP_DIR}/cpu-profile.trace"
    if rmrf(traceFile):
        print("Removed trace file")

    try:
        exec(
            "xcrun",
            "xctrace",
            "record",
            "--template",
            "Time Profiler",
            "--output",
            traceFile,
            "--target-stdout",
            "-",
            "--launch",
            "--",
            *cmd,
        )
    except Exception as e:
        if not os.path.exists(traceFile):
            raise e

    try:
        exec("open", traceFile)
    except Exception as e:
        raise e


def _profileMemLinux(cmd: list[str]):
    perfFile = f"{const.TMP_DIR}/mem-profile.data"
    exec("heaptrack", "-o", perfFile, *cmd)


def profile(cmd: list[str], rate=1000, what: str = "cpu"):
    if what not in ["cpu", "mem"]:
        raise RuntimeError("Only cpu and mem can be profile, not " + what)

    if what == "cpu":
        if platform.system() == "Linux":
            _profileCpuLinux(cmd, rate)
        elif platform.system() == "Darwin":
            _profileCpuDarwin(cmd, rate)
        else:
            raise RuntimeError(f"Unsupported platform {platform.system()}")
    elif what == "mem":
        if platform.system() == "Linux":
            _profileMemLinux(cmd)
        else:
            raise RuntimeError(f"Unsupported platform {platform.system()}")
    else:
        raise RuntimeError(f"Unknown profile type {what}")


def readdir(path: str) -> list[str]:
    _logger.debug(f"Reading directory {path}")

    try:
        return os.listdir(path)
    except FileNotFoundError:
        return []


def cp(src: str, dst: str):
    _logger.debug(f"Copying {src} to {dst}")

    shutil.copy(src, dst)


def mv(src: str, dst: str):
    _logger.debug(f"Moving {src} to {dst}")

    shutil.move(src, dst)


def cpTree(src: str, dst: str):
    _logger.debug(f"Copying {src} to {dst}")

    shutil.copytree(src, dst, dirs_exist_ok=True)


def cloneDir(url: str, path: str, dest: str) -> str:
    _logger.debug(f"Cloning {url} to {dest}")

    with tempfile.TemporaryDirectory() as tmp:
        mkdir(tmp)
        exec(
            *["git", "clone", "-n", "--depth=1", "--filter=tree:0", url, tmp],
            quiet=True,
        )
        exec(
            *["git", "-C", tmp, "sparse-checkout", "set", "--no-cone", path],
            quiet=True,
        )
        exec(*["git", "-C", tmp, "checkout", "-q", "--no-progress"], quiet=True)
        mv(os.path.join(tmp, path), dest)

    return dest


LATEST_CACHE: dict[str, str] = {}


@jexpr.exposed("shell.latest")
def latest(cmd: str) -> str:
    """
    Find the latest version of a command

    Exemples
    clang -> clang-15
    clang++ -> clang++-15
    gcc -> gcc10
    """

    global LATEST_CACHE

    if cmd in LATEST_CACHE:
        return LATEST_CACHE[cmd]

    if "IN_NIX_SHELL" in os.environ:
        # By default, NixOS symlinks tools automatically
        # to their latest version. Also, if the user uses
        # clang-xx, the std libraries will not be accessible.
        return cmd

    _logger.debug(f"Finding latest version of {cmd}")

    regex: re.Pattern[str]
    if platform.system() == "Windows":
        regex = re.compile(r"^" + re.escape(cmd) + r"(-.[0-9]+)?(\.exe)?$")
    else:
        regex = re.compile(r"^" + re.escape(cmd) + r"(-[0-9]+)?$")

    versions: list[str] = []
    for path in os.environ["PATH"].split(os.pathsep):
        if os.path.isdir(path):
            for f in os.listdir(path):
                if regex.match(f):
                    versions.append(f)

    if len(versions) == 0:
        raise RuntimeError(f"{cmd} not found")

    versions.sort()
    chosen = versions[-1]

    _logger.debug(f"Chosen {chosen} as latest version of {cmd}")

    LATEST_CACHE[cmd] = chosen

    return chosen


@jexpr.exposed("shell.which")
def which(cmd: str) -> Optional[str]:
    """
    Find the path of a command
    """
    return shutil.which(cmd)


@jexpr.exposed("shell.nproc")
def nproc() -> int:
    """
    Return the number of processors
    """
    return os.cpu_count() or 1


def gzip(path: str, dest: Optional[str] = None) -> str:
    """
    Compress a file or directory
    """
    if dest is None:
        dest = path + ".gz"

    with open(dest, "wb") as f:
        proc = subprocess.run(
            ["gzip", "-c", path],
            stdout=f,
            stderr=sys.stderr,
        )

    if proc.returncode != 0:
        raise RuntimeError(f"gzip: Process exited with code {proc.returncode}")

    return dest


def compress(path: str, dest: Optional[str] = None, format: str = "zstd") -> str:
    """
    Compress a file or directory
    """

    EXTS = {
        "zip": "zip",
        "zstd": "zst",
        "gzip": "gz",
    }

    if dest is None:
        dest = path + "." + EXTS[format]

    _logger.debug(f"Compressing {path} to {dest}")

    if format == "zip":
        exec("zip", "-r", dest, path)
    elif format == "zstd":
        exec("zstd", "-q", "-o", dest, path)
    elif format == "gzip":
        gzip(path, dest)
    else:
        raise RuntimeError(f"Unknown compression format {format}")

    return dest


_cwd = os.getcwd()


def restoreCwd():
    """
    Restore the current working directory to the one it was before
    cutekit was started
    """
    os.chdir(_cwd)


# --- Commands --------------------------------------------------------------- #


@cli.command("s", "shell", "Shell like commands")
def _():
    pass


class CommandArgs:
    cmd: str = cli.operand("command", "The command to debug")
    args: list[str] = cli.extra("args", "The arguments to pass to the command")

    def fullCmd(self) -> list[str]:
        return [self.cmd, *self.args]


class DebugArgs:
    wait: bool = cli.arg("w", "wait", "Wait for the debugger to attach")
    debugger: str = cli.arg(None, "debugger", "The debugger to use", default="lldb")


class _DebugArgs(DebugArgs, CommandArgs):
    pass


@cli.command("d", "shell/debug", "Debug a program")
def _(args: _DebugArgs):
    debug(args.fullCmd(), debugger=str(args.debugger), wait=args.wait)


class ProfileArgs:
    rate: int = cli.arg(None, "rate", "The sampling rate", default=1000)
    what: str = cli.arg(None, "what", "What to profile (cpu or mem)", default="cpu")


class _ProfileArgs(ProfileArgs, CommandArgs):
    pass


@cli.command("p", "shell/profile", "Profile a program")
def _(args: _ProfileArgs):
    profile(args.fullCmd(), rate=args.rate, what=args.what)


class CompressFormatArg:
    format: str = cli.arg(None, "format", "The compression format", default="zstd")


class CompresseArgs(CompressFormatArg):
    dest: Optional[str] = cli.arg(None, "dest", "The destination file or directory")
    path: str = cli.operand("path", "The file or directory to compress")


@cli.command("c", "shell/compress", "Compress a file or directory")
def _(args: CompresseArgs):
    compress(args.path, dest=args.dest, format=args.format)
