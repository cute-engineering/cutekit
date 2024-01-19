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
    shell,
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


class LoggerArgs:
    verbose = cli.Arg[bool]("v", "verbose", "Enable verbose logging", default=False)


class logger:
    @staticmethod
    def setup(args: LoggerArgs):
        if args.verbose:
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

            shell.mkdir(os.path.dirname(logFile))

            logging.basicConfig(
                level=logging.INFO,
                filename=logFile,
                filemode="w",
                format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )


class MainArgs(pods.PodArgs, plugins.PluginArgs, LoggerArgs):
    pass


@cli.command(None, "/", const.DESCRIPTION)
def _(args: MainArgs):
    shell.mkdir(const.GLOBAL_CK_DIR)
    logger.setup(args)
    const.setup()
    plugins.setup(args)
    pods.setup(args, sys.argv[1:])


def main() -> int:
    try:
        cli.exec(sys.argv)

        return 0
    except RuntimeError as e:
        logging.exception(e)
        cli.error(str(e))
        cli.usage()
    except KeyboardInterrupt:
        print()

    return 1
