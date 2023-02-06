import sys

from osdk import const
from osdk.args import parse
from osdk.cmds import exec, usage
from osdk.plugins import loadAll
import osdk.vt100 as vt100


def main() -> int:
    a = parse(sys.argv[1:])

    if not a.consumeOpt("verbose", False):
        sys.stderr = open(f"{const.OSDK_DIR}/osdk.log", "w")

    try:
        loadAll()
        exec(a)
        return 0
    except Exception as e:
        print(f"{vt100.RED}{e}{vt100.RESET}")
        print()

        usage()
        print()

        raise e
