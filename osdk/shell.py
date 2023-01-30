import os
import hashlib
import errno
import subprocess
import signal
import re
import shutil
import fnmatch

from osdk.logger import Logger
from osdk import const

logger = Logger("shell")


class Uname:
    def __init__(self, sysname: str, nodename: str, release: str, version: str, machine: str):
        self.sysname = sysname
        self.nodename = nodename
        self.release = release
        self.version = version
        self.machine = machine


def uname() -> Uname:
    un = os.uname()
    result = Uname(un.sysname, un.nodename, un.release, un.version, un.machine)
    if result.machine == "aarch64":
        result.machine = "arm64"
    return result


def sha256sum(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def find(path: str, wildcards: list[str] = []) -> list[str]:
    logger.log(f"Looking for files in {path} matching {wildcards}")

    if not os.path.isdir(path):
        return []

    result: list[str] = []

    for root, _, files in os.walk(path):
        for f in files:
            if len(wildcards) == 0:
                result.append(os.path.join(root, f))
            else:
                for wildcard in wildcards:
                    if fnmatch.fnmatch(f, wildcard):
                        result.append(os.path.join(root, f))
                        break

    return result


def mkdir(path: str) -> str:
    logger.log(f"Creating directory {path}")

    try:
        os.makedirs(path)
    except OSError as exc:
        if not (exc.errno == errno.EEXIST and os.path.isdir(path)):
            raise
    return path


def rmrf(path: str) -> bool:
    logger.log(f"Removing directory {path}")

    if not os.path.exists(path):
        return False
    shutil.rmtree(path, ignore_errors=True)
    return True


def wget(url: str, path: str | None = None) -> str:
    import requests

    if path is None:
        path = const.CACHE_DIR + "/" + \
            hashlib.sha256(url.encode('utf-8')).hexdigest()

    if os.path.exists(path):
        return path

    logger.log(f"Downloading {url} to {path}")

    r = requests.get(url, stream=True)
    r.raise_for_status()
    mkdir(os.path.dirname(path))
    with open(path, 'wb') as f:
        for chunk in r.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)

    return path


def exec(*args: str):
    logger.log(f"Executing {args}")

    try:
        proc = subprocess.run(args)

    except FileNotFoundError:
        raise Exception(f"Command not found")

    except KeyboardInterrupt:
        raise Exception("Interrupted")

    if proc.returncode == -signal.SIGSEGV:
        raise Exception("Segmentation fault")

    if proc.returncode != 0:
        raise Exception(f"Process exited with code {proc.returncode}")

    return True


def popen(*args: str) -> str:
    logger.log(f"Executing {args}")

    try:
        proc = subprocess.run(args, stdout=subprocess.PIPE)
    except FileNotFoundError:
        raise Exception(f"Command not found")

    if proc.returncode == -signal.SIGSEGV:
        raise Exception("Segmentation fault")

    if proc.returncode != 0:
        raise Exception(f"Process exited with code {proc.returncode}")

    return proc.stdout.decode('utf-8')


def readdir(path: str) -> list[str]:
    logger.log(f"Reading directory {path}")

    try:
        return os.listdir(path)
    except FileNotFoundError:
        return []


def cp(src: str, dst: str):
    logger.log(f"Copying {src} to {dst}")

    shutil.copy(src, dst)


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

    logger.log(f"Finding latest version of {cmd}")

    regex = re.compile(r"^" + re.escape(cmd) + r"(-.[0-9]+)?$")

    versions: list[str] = []
    for path in os.environ["PATH"].split(os.pathsep):
        if os.path.isdir(path):
            for f in os.listdir(path):
                if regex.match(f):
                    versions.append(f)

    if len(versions) == 0:
        raise Exception(f"{cmd} not found")

    versions.sort()
    chosen = versions[-1]

    logger.log(f"Chosen {chosen} as latest version of {cmd}")

    LATEST_CACHE[cmd] = chosen

    return chosen
