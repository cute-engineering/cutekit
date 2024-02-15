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
    print(f"{RED}Error:{RESET} {msg}\n", file=sys.stderr)


def warning(msg: str) -> None:
    print(f"{YELLOW}Warning:{RESET} {msg}\n", file=sys.stderr)


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
