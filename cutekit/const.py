import os
import sys
from pathlib import Path

VERSION = (0, 6, 0, "dev")
VERSION_STR = (
    f"{VERSION[0]}.{VERSION[1]}.{VERSION[2]}{'-' + VERSION[3] if VERSION[3] else ''}"
)
ARGV0 = Path(sys.argv[0])
PROJECT_CK_DIR = Path(".cutekit")
GLOBAL_CK_DIR = Path.home() / ".cutekit"
BUILD_DIR = PROJECT_CK_DIR / "build"
CACHE_DIR = PROJECT_CK_DIR / "cache"
EXTERN_DIR = PROJECT_CK_DIR / "extern"
SRC_DIR = Path("src")
META_DIR = Path("meta")
TARGETS_DIR = META_DIR / "targets"
DEFAULT_REPO_TEMPLATES = "cute-engineering/cutekit-templates"
DESCRIPTION = "A build system and package manager for low-level software development"
PROJECT_LOG_FILE = PROJECT_CK_DIR / "cutekit.log"
GLOBAL_LOG_FILE = GLOBAL_CK_DIR / "cutekit.log"
