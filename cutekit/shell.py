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

from typing import Optional
from . import const

_logger = logging.getLogger(__name__)


@dt.dataclass
class Uname:
    sysname: str
    nodename: str
    release: str
    version: str
    machine: str


def uname() -> Uname:
    un = platform.uname()
    result = Uname(un.system, un.node, un.release, un.version, un.machine)

    match result.machine:
        case "aarch64":
            result.machine = "arm64"
        case "AMD64":
            result.machine = "x86_64"
        case _:
            pass

    return result


def sha256sum(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def find(
    path: str | list[str], wildcards: list[str] = [], recusive: bool = True
) -> list[str]:
    _logger.debug(f"Looking for files in {path} matching {wildcards}")

    result: list[str] = []

    if isinstance(path, list):
        for p in path:
            result += find(p, wildcards, recusive)
        return result

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

    return result


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
        raise RuntimeError(f"{args[0]}: Interrupted")

    if proc.returncode == -signal.SIGSEGV:
        raise RuntimeError(f"{args[0]}: Segmentation fault")

    if proc.returncode != 0:
        raise RuntimeError(f"{args[0]}: Process exited with code {proc.returncode}")

    return True


def popen(*args: str) -> str:
    _logger.debug(f"Executing {args}")

    try:
        proc = subprocess.run(args, stdout=subprocess.PIPE, stderr=sys.stderr)
    except FileNotFoundError:
        raise RuntimeError(f"{args[0]}: Command not found")

    if proc.returncode == -signal.SIGSEGV:
        raise RuntimeError(f"{args[0]}: Segmentation fault")

    if proc.returncode != 0:
        raise RuntimeError(f"{args[0]}: Process exited with code {proc.returncode}")

    return proc.stdout.decode("utf-8").strip()


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
    with tempfile.TemporaryDirectory() as tmp:
        mkdir(tmp)
        exec(
            *["git", "clone", "-n", "--depth=1", "--filter=tree:0", url, tmp, "-q"],
            quiet=True,
        )
        exec(
            *["git", "-C", tmp, "sparse-checkout", "set", "--no-cone", path, "-q"],
            quiet=True,
        )
        exec(*["git", "-C", tmp, "checkout", "-q", "--no-progress"], quiet=True)
        mv(os.path.join(tmp, path), dest)

    return dest


LATEST_CACHE: dict[str, str] = {}


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


def which(cmd: str) -> Optional[str]:
    """
    Find the path of a command
    """
    return shutil.which(cmd)


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
