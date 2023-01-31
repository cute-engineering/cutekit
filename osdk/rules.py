class Rule:
    id: str
    fileIn: list[str]
    fileOut: list[str]
    rule: str

    def __init__(self, id: str, fileIn: list[str], fileOut: list[str], rule: str):
        self.id = id
        self.fileIn = fileIn
        self.fileOut = fileOut
        self.rule = rule


rules: dict[str, Rule] = {
    "cc": Rule("cc", ["c"], ["o"], "-c -o $out $in -MD -MF $out.d $flags"),
    "cxx": Rule("cxx", ["cpp", "cc", "cxx"], ["o"], "-c -o $out $in -MD -MF $out.d $flags"),
    "as": Rule("as", ["s", "asm", "S"], ["o"], "-o $out $in $flags"),
    "ar": Rule("ar", ["o"], ["a"], "$flags $out $in"),
    "ld": Rule("ld", ["o", "a"], ["out"], "$flags $out $in"),
}


def append(rule: Rule):
    rules[rule.id] = rule


def byFileIn(fileIn: str) -> Rule | None:
    for key in rules:
        rule = rules[key]
        for ext in rule.fileIn:
            if fileIn.endswith("." + ext):
                return rule
    return None


def byId(id: str) -> Rule | None:
    return rules.get(id, None)
