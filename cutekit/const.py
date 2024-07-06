import os

from . import utils


class Uninitialized:
    def __repr__(self):
        raise Exception("Uninitialized constant")

    def __str__(self):
        raise Exception("Uninitialized constant")

    def __bool__(self):
        raise Exception("Uninitialized constant")


VERSION = (0, 7, 4)
VERSION_STR = f"{VERSION[0]}.{VERSION[1]}.{VERSION[2]}{'-' +  str(VERSION[-1]) if len(VERSION) > 3 else ''}"
MODULE_DIR = os.path.dirname(os.path.realpath(__file__))


ARGV0 = "cutekit"
PROJECT_CK_DIR = ".cutekit"
GLOBAL_CK_DIR = os.path.join(os.path.expanduser("~"), ".cutekit")
BUILD_DIR = os.path.join(PROJECT_CK_DIR, "build")
CACHE_DIR = os.path.join(PROJECT_CK_DIR, "cache")
EXTERN_DIR = os.path.join(PROJECT_CK_DIR, "extern")
GENERATED_DIR = os.path.join(PROJECT_CK_DIR, "generated")
TMP_DIR = os.path.join(PROJECT_CK_DIR, "tmp")
SRC_DIR = "src"
META_DIR = "meta"
TARGETS_DIR = os.path.join(META_DIR, "targets")
DEFAULT_REPO_TEMPLATES = "cute-engineering/cutekit-templates"
DESCRIPTION = "A build system and package manager for low-level software development"
PROJECT_LOG_FILE = os.path.join(PROJECT_CK_DIR, "cutekit.log")
GLOBAL_LOG_FILE: str = os.path.join(os.path.expanduser("~"), ".cutekit", "cutekit.log")
HOSTID: str | Uninitialized = Uninitialized()


def setup():
    global HOSTID
    hostIdPath = GLOBAL_CK_DIR + "/hostid"
    if os.path.exists(hostIdPath):
        with open(hostIdPath, "r") as f:
            HOSTID = f.read().strip()
    else:
        HOSTID = utils.randomHash()
        with open(hostIdPath, "w") as f:
            f.write(HOSTID)
