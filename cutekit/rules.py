import dataclasses as dt

from typing import Optional


@dt.dataclass
class Rule:
    id: str
    fileIn: list[str]
    fileOut: str
    rule: str
    args: list[str] = dt.field(default_factory=list)
    deps: list[str] = dt.field(default_factory=list)


rules: dict[str, Rule] = {
    "cp": Rule("cp", ["*"], "*", "$in $out"),
    "cc": Rule(
        "cc",
        ["*.c"],
        "*.o",
        "-c -o $out $in -MD -MF $out.d $flags $cincs $cdefs",
        [
            "-std=gnu2x",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-fcolor-diagnostics",
        ],
        ["$out.d"],
    ),
    "cxx": Rule(
        "cxx",
        ["*.cpp", "*.cc", "*.cxx"],
        "*.o",
        "-c -o $out $in -MD -MF $out.d $flags $cincs $cdefs",
        [
            "-std=gnu++2b",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-fcolor-diagnostics",
            "-fno-exceptions",
            "-fno-rtti",
        ],
        ["$out.d"],
    ),
    "as": Rule("as", ["*.s", "*.asm", "*.S"], "*.o", "-o $out $in $flags"),
    "ar": Rule("ar", ["*.o"], "*.a", "$flags $out $in"),
    "ld": Rule(
        "ld",
        ["*.o", "*.a"],
        "*.out",
        "-o $out $objs -Wl,--whole-archive $wholeLibs -Wl,--no-whole-archive $libs $flags",
    ),
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
