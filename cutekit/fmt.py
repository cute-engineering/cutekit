from pathlib import Path
from . import cli, shell


class FmtArgs:
    fix: bool = cli.arg("f", "fix", "Fix formatting issues", False)


@cli.command("fmt", "Format source code")
def _(args: FmtArgs):
    command = [shell.latest("clang-format")]

    if args.fix:
        command.append("-i")
    else:
        command.append("--dry-run")
        command.append("--Werror")

    command.extend(shell.find("src", ["*.c", "*.h", "*.cpp", "*.hpp", "*.cc", "*.hh"]))
    shell.exec(*command)


class LintArgs:
    fix: bool = cli.arg("f", "fix", "Fix linting issues", False)


@cli.command("lint", "Lint source code")
def _(args: LintArgs):
    command = ["clang-tidy"]
    if Path("src/.clang-tidy").exists():
        command.append("--config-file=src/.clang-tidy")

    if args.fix:
        command.append("-fix")

    command.extend(shell.find("src", ["*.c", "*.h", "*.cpp", "*.hpp", "*.cc", "*.hh"]))
    shell.exec(*command)
