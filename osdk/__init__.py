import sys


from osdk.args import parse
from osdk.cmds import exec, usage
from osdk.plugins import loadAll
import osdk.vt100 as vt100


def main() -> int:
    try:
        loadAll()
        a = parse(sys.argv[1:])
        exec(a)
        return 0
    except Exception as e:
        print(f"{vt100.RED}{e}{vt100.RESET}")
        print()

        usage()
        print()

        raise e
