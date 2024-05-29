from pathlib import Path
from . import utils


class Uninitialized:
    def __repr__(self):
        raise Exception("Uninitialized constant")

    def __str__(self):
        raise Exception("Uninitialized constant")

    def __bool__(self):
        raise Exception("Uninitialized constant")


VERSION = (0, 8, 0, "dev")
VERSION_STR = f"{VERSION[0]}.{VERSION[1]}.{VERSION[2]}{'-' + VERSION[3] if len(VERSION) >= 4 else ''}"
MODULE_DIR = Path(__file__).absolute().parent


ARGV0 = "cutekit"
PROJECT_CK_DIR = Path(".cutekit")
GLOBAL_CK_DIR = Path.home() / ".cutekit"

BUILD_DIR = PROJECT_CK_DIR / "build"
CACHE_DIR = PROJECT_CK_DIR / "cache"
EXTERN_DIR = PROJECT_CK_DIR / "extern"
GENERATED_DIR = PROJECT_CK_DIR / "generated"
TMP_DIR = PROJECT_CK_DIR / "tmp"
SRC_DIR = Path("src")
META_DIR = Path("meta")
TARGETS_DIR = META_DIR / "targets"

DEFAULT_REPO_TEMPLATES = "cute-engineering/cutekit-templates"
DESCRIPTION = "A build system and package manager for low-level software development"
PROJECT_LOG_FILE = "cutekit.log"
GLOBAL_LOG_FILE = GLOBAL_CK_DIR / "cutekit.log"
HOSTID: str | Uninitialized = Uninitialized()


def setup():
    global HOSTID
    hostIdPath = GLOBAL_CK_DIR / "hostid"
    if hostIdPath.exists():
        with hostIdPath.open("r") as f:
            HOSTID = f.read().strip()
    else:
        HOSTID = utils.randomHash()
        with open(hostIdPath, "w") as f:
            f.write(HOSTID)
