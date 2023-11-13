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


from pathlib import Path
from typing import Optional
from . import const

_logger = logging.getLogger(__name__)


class Uname:
    def __init__(
        self, sysname: str, nodename: str, release: str, version: str, machine: str
    ):
        self.sysname = sysname
        self.nodename = nodename
        self.release = release
        self.version = version
        self.machine = machine


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


def rmrf(path: Path) -> bool:
    _logger.info(f"Removing directory {path}")

    if not path.exists():
        return False
    shutil.rmtree(path, ignore_errors=True)
    return True


def wget(url: str, path: Optional[Path] = None) -> Path:
    import requests

    if path is None:
        path = const.CACHE_DIR / hashlib.sha256(url.encode("utf-8")).hexdigest()

    if path.exists():
        return path

    _logger.info(f"Downloading {url} to {path}")

    r = requests.get(url, stream=True)
    r.raise_for_status()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)

    return path


def exec(*args: str, quiet: bool = False) -> bool:
    _logger.info(f"Executing {args}")

    try:
        proc = subprocess.run(
            args,
            stdout=sys.stdout if not quiet else subprocess.PIPE,
            stderr=sys.stderr if not quiet else subprocess.PIPE,
        )

        if proc.stdout:
            _logger.info(proc.stdout.decode("utf-8"))

        if proc.stderr:
            _logger.error(proc.stderr.decode("utf-8"))

    except FileNotFoundError:
        raise RuntimeError(f"{args[0]}: Command not found")

    except KeyboardInterrupt:
        raise RuntimeError(f"{args[0]}: Interrupted")

    if proc.returncode == -signal.SIGSEGV:
        raise RuntimeError(f"{args[0]}: Segmentation fault")

    if proc.returncode != 0:
        raise RuntimeError(f"{args[0]}: Process exited with code {proc.returncode}")

    return True


def popen(*args: str) -> str:
    _logger.info(f"Executing {args}")

    try:
        proc = subprocess.run(args, stdout=subprocess.PIPE, stderr=sys.stderr)
    except FileNotFoundError:
        raise RuntimeError(f"{args[0]}: Command not found")

    if proc.returncode == -signal.SIGSEGV:
        raise RuntimeError(f"{args[0]}: Segmentation fault")

    if proc.returncode != 0:
        raise RuntimeError(f"{args[0]}: Process exited with code {proc.returncode}")

    return proc.stdout.decode("utf-8")


def cp(src: Path, dst: Path):
    _logger.info(f"Copying {src} to {dst}")

    shutil.copy(src, dst)


def mv(src: Path, dst: Path):
    _logger.info(f"Moving {src} to {dst}")

    shutil.move(src, dst)


def cpTree(src: Path, dst: Path):
    _logger.info(f"Copying {src} to {dst}")

    shutil.copytree(src, dst, dirs_exist_ok=True)


def cloneDir(url: str, path: Path, dest: Path) -> Path:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        tmp.mkdir(parents=True, exist_ok=True)
        exec(
            *["git", "clone", "-n", "--depth=1", "--filter=tree:0", url, tmp, "-q"],
            quiet=True,
        )
        exec(
            *["git", "-C", tmp, "sparse-checkout", "set", "--no-cone", path, "-q"],
            quiet=True,
        )
        exec(*["git", "-C", tmp, "checkout", "-q", "--no-progress"], quiet=True)
        mv(tmp / path, dest)

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

    _logger.info(f"Finding latest version of {cmd}")

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

    _logger.info(f"Chosen {chosen} as latest version of {cmd}")

    LATEST_CACHE[cmd] = chosen

    return chosen


def which(cmd: str) -> Optional[str]:
    """
    Find the path of a command
    """
    return shutil.which(cmd)
