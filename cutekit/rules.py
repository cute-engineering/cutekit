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
        "-MD -MF $out.d $flags $cincs $cdefs -c -o $out $in",
        [
            "-std=gnu2y",
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
        "-MD -MF $out.d $flags $cincs $cdefs $modmap -c -o $out $in",
        [
            "-std=gnu++2c",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-fcolor-diagnostics",
            "-fmodules-reduced-bmi",
        ],
        ["$out.d"],
    ),
    "cxx-scan": Rule(
        "cxx-scan",
        ["*.cpp", "*.cc", "*.cxx"],
        "*.ddi",
        "-format=p1689 -- clang++ -x c++ -c -o $obj $in -MT $out -MD -MF $out.d $cxxflags $cincs $cdefs > $out.tmp && mv $out.tmp $out",
        [],
        ["$out.d"],
    ),
    "cxx-collect": Rule(
        "cxx-collect",
        ["*.ddi"],
        "*.dd",
        "-s '.' $in > $out.tmp && mv $out.tmp $out",
        [],
        [],
    ),
    "cxx-modmap": Rule(
        "cxx-modmap",
        ["*.cpp"],
        "*.dd",
        "$obj --dir=$builddir --deps=$builddir/modules.ddi > $out.tmp && mv $out.tmp $out",
        [],
        [],
    ),
    "cxx-dyndep": Rule(
        "cxx-dyndep",
        ["*.dd"],
        "*.dd",
        "--dir=$builddir --deps=$builddir/modules.ddi > $out.tmp && mv $out.tmp $out",
        [],
        [],
    ),
    "as": Rule("as", ["*.s", "*.asm", "*.S"], "*.o", "-o $out $in $flags"),
    "ar": Rule("ar", ["*.o"], "*.a", "$flags $out $in"),
    "ld": Rule(
        "ld",
        ["*.o", "*.a"],
        "*.out",
        "-o $out $objs $libs $flags",
    ),
    "ld-shared": Rule(
        "ld-shared",
        ["*.o", "*.a"],
        "*.so",
        "-shared -o $out $objs $libs $flags",
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
