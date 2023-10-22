import sys
import os
import logging

from cutekit import const, project, vt100, plugins, cmds
from cutekit.args import parse

def setupLogger(verbose: bool):
    if verbose:
        logging.basicConfig(
            level=logging.INFO,
            format=f"{vt100.CYAN}%(asctime)s{vt100.RESET} {vt100.YELLOW}%(levelname)s{vt100.RESET} %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    else:
        projectRoot = project.root()
        logFile = const.GLOBAL_LOG_FILE
        if projectRoot is not None:
            logFile = os.path.join(projectRoot, const.PROJECT_LOG_FILE)

        # create the directory if it doesn't exist
        logDir = os.path.dirname(logFile)
        if not os.path.isdir(logDir):
            os.makedirs(logDir)

        logging.basicConfig(
            level=logging.INFO,
            filename=logFile,
            filemode="w",
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

def main() -> int:
    try:
        a = parse(sys.argv[1:])
        setupLogger(a.consumeOpt("verbose", False) is True)
        plugins.loadAll()
        cmds.exec(a)
        print()
        return 0
    except RuntimeError as e:
        logging.exception(e)
        cmds.error(str(e))
        cmds.usage()
        print()
        return 1
    except KeyboardInterrupt:
        print()
        return 1
