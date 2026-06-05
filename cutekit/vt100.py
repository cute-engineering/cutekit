import sys
from typing import Optional


BLACK = "\033[30m"
RED = "\033[31m"
GREEN = "\033[32m"
BROWN = "\033[33m"
BLUE = "\033[34m"
PURPLE = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"
YELLOW = "\033[33m"


BRIGHT_BLACK = "\033[90m"
BRIGHT_RED = "\033[91m"
BRIGHT_GREEN = "\033[92m"
BRIGHT_BROWN = "\033[93m"
BRIGHT_BLUE = "\033[94m"
BRIGHT_PURPLE = "\033[95m"
BRIGHT_CYAN = "\033[96m"
BRIGHT_WHITE = "\033[97m"

BOLD = "\033[1m"
FAINT = "\033[2m"
ITALIC = "\033[3m"
UNDERLINE = "\033[4m"
BLINK = "\033[5m"
NEGATIVE = "\033[7m"
CROSSED = "\033[9m"
RESET = "\033[0m"


def wordwrap(text: str, width: int = 60, newline: str = "\n") -> str:
    result = ""
    curr = 0

    for c in text:
        if c == " " and curr > width:
            result += newline
            curr = 0
        else:
            result += c
            curr += 1

    return result


def indent(text: str, indent: int = 4) -> str:
    return " " * indent + text.replace("\n", "\n" + " " * indent)


def title(text: str):
    print(f"{BOLD+WHITE+UNDERLINE}{text}{RESET}")


def subtitle(text: str):
    print(f"{BOLD+WHITE}{text}{RESET}:")


def p(text: str):
    return indent(wordwrap(text))


def error(msg: str) -> None:
    print(f"{RED}Error:{RESET} {msg}", file=sys.stderr)


def warning(msg: str) -> None:
    print(f"{YELLOW}Warning:{RESET} {msg}", file=sys.stderr)


def formatSize(size: int) -> str:
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    value = float(size)

    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024

    return f"{size} B"


def printProgress(label: str, current: int, total: int):
    if total > 0:
        percent = min(max(current / total, 0), 1)
        message = (
            f"\r{label}: {percent * 100:5.1f}% "
            f"({formatSize(current)}/{formatSize(total)})"
        )
    else:
        message = f"\r{label}: {formatSize(current)}"

    print(message, end="", file=sys.stderr, flush=True)


def finishProgress(label: str, current: int, total: int):
    printProgress(label, current, total)
    print(file=sys.stderr, flush=True)


def ask(msg: str, default: Optional[bool] = None) -> bool:
    if default is None:
        msg = f"{msg} [y/n] "
    elif default:
        msg = f"{msg} [Y/n] "
    else:
        msg = f"{msg} [y/N] "

    while True:
        result = input(msg).lower()
        if result in ("y", "yes"):
            return True
        elif result in ("n", "no"):
            return False
        elif result == "" and default is not None:
            return default

def rgb(r: int, g: int, b: int) -> str:
    return f"\033[38;2;{r};{g};{b}m"
