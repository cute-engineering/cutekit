import sys
import os
import logging

from . import (
    builder,  # noqa: F401 this is imported for side effects
    cli,
    const,
    graph,  # noqa: F401 this is imported for side effects
    model,
    plugins,
    pods,  # noqa: F401 this is imported for side effects
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
            level=logging.DEBUG,
            format=f"{vt100.CYAN}%(asctime)s{vt100.RESET} {vt100.YELLOW}%(levelname)s{vt100.RESET} %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    else:
        projectRoot = model.Project.topmost()
        logFile = const.GLOBAL_LOG_FILE
        if projectRoot is not None:
            logFile = os.path.join(projectRoot.dirname(), const.PROJECT_LOG_FILE)

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
        args = cli.parse(sys.argv[1:])
        setupLogger(args.consumeOpt("verbose", False) is True)
        safemode = args.consumeOpt("safemode", False) is True
        if not safemode:
            plugins.loadAll()
        pods.reincarnate(args)
        cli.exec(args)
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
