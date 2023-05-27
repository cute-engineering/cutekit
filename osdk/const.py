import os
import sys

VERSION = "0.4.1"
MODULE_DIR = os.path.dirname(os.path.realpath(__file__))
ARGV0 = os.path.basename(sys.argv[0])
OSDK_DIR = ".osdk"
BUILD_DIR = os.path.join(OSDK_DIR, "build")
CACHE_DIR = os.path.join(OSDK_DIR, "cache")
EXTERN_DIR = os.path.join(OSDK_DIR, "extern")
SRC_DIR = "src"
META_DIR = f"meta"
TARGETS_DIR = os.path.join(META_DIR, "targets")
DEFAULT_REPO_TEMPLATES = "cute-engineering/osdk-template"