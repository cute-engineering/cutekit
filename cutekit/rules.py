from typing import Optional


class Rule:
    id: str
    fileIn: list[str]
    fileOut: list[str]
    rule: str
    args: list[str]
    deps: Optional[str] = None

    def __init__(
        self,
        id: str,
        fileIn: list[str],
        fileOut: list[str],
        rule: str,
        args: list[str] = [],
        deps: Optional[str] = None,
    ):
        self.id = id
        self.fileIn = fileIn
        self.fileOut = fileOut
        self.rule = rule
        self.args = args
        self.deps = deps


rules: dict[str, Rule] = {
    "cc": Rule(
        "cc",
        ["*.c"],
        ["*.o"],
        "-c -o $out $in -MD -MF $out.d $flags $cincs $cdefs",
        ["-std=gnu2x", "-Wall", "-Wextra", "-Werror"],
        "$out.d",
    ),
    "cxx": Rule(
        "cxx",
        ["*.cpp", "*.cc", "*.cxx"],
        ["*.o"],
        "-c -o $out $in -MD -MF $out.d $flags $cincs $cdefs",
        ["-std=gnu++2b", "-Wall", "-Wextra", "-Werror", "-fno-exceptions", "-fno-rtti"],
        "$out.d",
    ),
    "as": Rule("as", ["*.s", "*.asm", "*.S"], ["*.o"], "-o $out $in $flags"),
    "ar": Rule("ar", ["*.o"], ["*.a"], "$flags $out $in"),
    "ld": Rule("ld", ["*.o", "*.a"], ["*.out"], "-o $out $in $flags"),
}


def append(rule: Rule):
    rules[rule.id] = rule


def byFileIn(fileIn: str) -> Optional[Rule]:
    for key in rules:
        rule = rules[key]
        for ext in rule.fileIn:
            if fileIn.endswith(ext[1:]):
                return rule
    return None


def byId(id: str) -> Optional[Rule]:
    return rules.get(id, None)
