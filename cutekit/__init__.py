import sys
import os
import logging

from . import (
    builder,
    cli,
    compat,
    const,
    graph,
    jexpr,
    mixins,
    model,
    ninja,
    plugins,
    rules,
    shell,
    utils,
    vt100,
)


def ensure(version: tuple[int, int, int]):
    if (
        const.VERSION[0] == version[0]
        and const.VERSION[1] == version[1]
        and const.VERSION[2] >= version[2]
    ):
        return

    raise RuntimeError(
        f"Expected cutekit version {version[0]}.{version[1]}.{version[2]} but found {const.VERSION_STR}"
    )


def setupLogger(verbose: bool):
    if verbose:
        logging.basicConfig(
            level=logging.INFO,
            format=f"{vt100.CYAN}%(asctime)s{vt100.RESET} {vt100.YELLOW}%(levelname)s{vt100.RESET} %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    else:
        projectRoot = model.Project.root()
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
        a = cli.parse(sys.argv[1:])
        setupLogger(a.consumeOpt("verbose", False) is True)
        plugins.loadAll()
        cli.exec(a)
        print()
        return 0
    except RuntimeError as e:
        logging.exception(e)
        cli.error(str(e))
        cli.usage()
        print()
        return 1
    except KeyboardInterrupt:
        print()
        return 1
