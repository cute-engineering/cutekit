import os
import sys

VERSION = "0.4.0"
MODULE_DIR = os.path.dirname(os.path.realpath(__file__))
ARGV0 = os.path.basename(sys.argv[0])
OSDK_DIR = ".osdk"
BUILD_DIR = f"{OSDK_DIR}/build"
CACHE_DIR = f"{OSDK_DIR}/cache"
SRC_DIR = "src/"
META_DIR = f"meta"
TARGETS_DIR = f"{META_DIR}/targets"
