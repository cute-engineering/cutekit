import sys
import osdk.vt100 as vt100


class Logger:
    name: str

    def __init__(self, name: str):
        self.name = name

    def log(self, message: str):
        print(
            f"{vt100.CYAN}[{self.name}]{vt100.RESET} {message}", file=sys.stderr)

    def warn(self, message: str):
        print(
            f"{vt100.YELLOW}[{self.name}]{vt100.RESET} {message}", file=sys.stderr)

    def error(self, message: str):
        print(
            f"{vt100.RED}[{self.name}]{vt100.RESET} {message}", file=sys.stderr)
