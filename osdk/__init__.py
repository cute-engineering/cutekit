import sys
import logging

from os.path import isdir
from osdk import const, shell
from osdk.args import parse
from osdk.cmds import exec, usage
from osdk.plugins import loadAll
import osdk.vt100 as vt100


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format=f"{vt100.CYAN}%(asctime)s{vt100.RESET} {vt100.YELLOW}%(levelname)s{vt100.RESET} %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    a = parse(sys.argv[1:])


    try:
        loadAll()
        exec(a)
        return 0
    except Exception as e:
        logging.error(f"{vt100.RED}{e}{vt100.RESET}")
        print()

        usage()
        print()

        raise e
