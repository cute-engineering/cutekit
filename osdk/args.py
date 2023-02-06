Value = str | bool | int


class Args:
    opts: dict[str, Value]
    args: list[str]

    def __init__(self):
        self.opts = {}
        self.args = []

    def consumePrefix(self, prefix: str) -> dict[str, Value]:
        result: dict[str, Value] = {}
        for key, value in self.opts.items():
            if key.startswith(prefix):
                result[key[len(prefix):]] = value
                del self.opts[key]
        return result

    def consumeOpt(self, key: str, default: Value) -> Value:
        if key in self.opts:
            result = self.opts[key]
            del self.opts[key]
            return result
        return default

    def tryConsumeOpt(self, key: str) -> Value | None:
        if key in self.opts:
            result = self.opts[key]
            del self.opts[key]
            return result
        return None

    def consumeArg(self) -> str | None:
        if len(self.args) == 0:
            return None

        first = self.args[0]
        del self.args[0]
        return first


def parse(args: list[str]) -> Args:
    result = Args()

    for arg in args:
        if arg.startswith("--"):
            if "=" in arg:
                key, value = arg[2:].split("=", 1)
                result.opts[key] = value
            else:
                result.opts[arg[2:]] = True
        else:
            result.args.append(arg)

    return result
