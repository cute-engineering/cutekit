from enum import Enum
import os
import sys
from types import GenericAlias
import typing as tp
import dataclasses as dt
import logging

from typing import Any, Callable, Optional
from cutekit import vt100, const, utils

_logger = logging.getLogger(__name__)

# --- Scan -------------------------------------------------------------- #


class Scan:
    _src: str
    _off: int
    _save: list[int]

    def __init__(self, src: str, off: int = 0):
        self._src = src
        self._off = 0
        self._save = []

    def curr(self) -> str:
        if self.eof():
            return "\0"
        return self._src[self._off]

    def next(self) -> str:
        if self.eof():
            return "\0"

        self._off += 1
        return self.curr()

    def peek(self, off: int = 1) -> str:
        if self._off + off >= len(self._src):
            return "\0"

        return self._src[self._off + off]

    def eof(self) -> bool:
        return self._off >= len(self._src)

    def skipStr(self, s: str) -> bool:
        if self._src[self._off :].startswith(s):
            self._off += len(s)
            return True

        return False

    def isStr(self, s: str) -> bool:
        self.save()
        if self.skipStr(s):
            self.restore()
            return True

        self.restore()
        return False

    def save(self) -> None:
        self._save.append(self._off)

    def restore(self) -> None:
        self._off = self._save.pop()

    def skipWhitespace(self) -> bool:
        result = False
        while not self.eof() and self.curr().isspace():
            self.next()
            result = True
        return result

    def skipSeparator(self, sep: str) -> bool:
        self.save()
        self.skipWhitespace()
        if self.skipStr(sep):
            self.skipWhitespace()
            return True

        self.restore()
        return False

    def isSeparator(self, sep: str) -> bool:
        self.save()
        self.skipWhitespace()
        if self.skipStr(sep):
            self.skipWhitespace()
            self.restore()
            return True

        self.restore()
        return False

    def skipKeyword(self, keyword: str) -> bool:
        self.save()
        self.skipWhitespace()
        if self.skipStr(keyword) and not self.curr().isalnum():
            return True

        self.restore()
        return False

    def isKeyword(self, keyword: str) -> bool:
        self.save()
        self.skipWhitespace()
        if self.skipStr(keyword) and not self.curr().isalnum():
            self.restore()
            return True

        self.restore()
        return False


# --- Parser ------------------------------------------------------------ #

PrimitiveValue = str | bool | int
Object = dict[str, PrimitiveValue]
List = list[PrimitiveValue]
Value = str | bool | int | Object | List


@dt.dataclass
class Token:
    pass


@dt.dataclass
class ArgumentToken(Token):
    key: str
    subkey: Optional[str]
    value: Value
    short: bool


@dt.dataclass
class OperandToken(Token):
    value: str


@dt.dataclass
class ExtraToken(Token):
    args: list[str]


def _parseIdent(s: Scan) -> str:
    res = ""
    while not s.eof() and (s.curr().isalnum() or s.curr() in "_-+"):
        res += s.curr()
        s.next()
    return res


def _parseUntilComma(s: Scan) -> str:
    res = ""
    while not s.eof() and s.curr() != ",":
        res += s.curr()
        s.next()
    return res


def _expectIdent(s: Scan) -> str:
    res = _parseIdent(s)
    if len(res) == 0:
        raise RuntimeError("Expected identifier")
    return res


def _parseString(s: Scan, quote: str) -> str:
    s.skipStr(quote)
    res = ""
    escaped = False
    while not s.eof():
        c = s.curr()
        if escaped:
            res += c
            escaped = False
        elif c == "\\":
            escaped = True
        elif c == quote:
            break
        else:
            res += c
        s.next()
    if not s.skipStr(quote):
        raise RuntimeError("Unterminated string")
    return res


def _tryParseInt(ident) -> Optional[int]:
    try:
        return int(ident)
    except ValueError:
        return None


def _parsePrimitive(s: Scan) -> PrimitiveValue:
    if s.curr() == '"':
        return _parseString(s, '"')
    elif s.curr() == "'":
        return _parseString(s, "'")
    else:
        ident = _parseUntilComma(s)

        if ident in ("true", "True", "y", "yes", "Y", "Yes"):
            return True
        elif ident in ("false", "False", "n", "no", "N", "No"):
            return False
        elif n := _tryParseInt(ident):
            return n
        else:
            return ident


def _parseValue(s: Scan) -> Value:
    lhs = _parsePrimitive(s)
    if s.eof():
        return lhs
    values: List = [lhs]
    while not s.eof() and s.skipStr(","):
        values.append(_parsePrimitive(s))
    return values


def parseValue(s: str) -> Value:
    return _parseValue(Scan(s))


def parseArg(arg: str) -> list[Token]:
    s = Scan(arg)
    if s.skipStr("--"):
        key = _expectIdent(s)
        subkey = ""
        if s.skipStr(":"):
            subkey = _expectIdent(s)
        if s.skipStr("="):
            value = _parseValue(s)
        else:
            value = True
        return [ArgumentToken(key, subkey, value, False)]
    elif s.skipStr("-"):
        res = []
        while not s.eof():
            key = s.curr()
            if not key.isalnum():
                raise RuntimeError("Expected alphanumeric")
            s.next()
            res.append(ArgumentToken(key, None, True, True))
        return tp.cast(list[Token], res)
    else:
        return [OperandToken(arg)]


def parseArgs(args: list[str]) -> list[Token]:
    res: list[Token] = []
    while len(args) > 0:
        arg = args.pop(0)
        if arg == "--":
            res.append(ExtraToken(args))
            break
        else:
            res.extend(parseArg(arg))
    return res


# --- Schema ----------------------------------------------------------------- #


class FieldKind(Enum):
    FLAG = 0
    OPERAND = 1
    EXTRA = 2


@dt.dataclass
class Field:
    kind: FieldKind
    shortName: Optional[str]
    longName: str
    description: str = ""
    default: Any = None

    _fieldName: str | None = dt.field(init=False, default=None)
    _fieldType: type | None = dt.field(init=False, default=None)

    def bind(self, typ: type, name: str):
        self._fieldName = name
        self._fieldType = typ.__annotations__[name]
        if self.longName is None:
            self.longName = name

    def isBool(self) -> bool:
        return self._fieldType == bool

    def isList(self) -> bool:
        return (
            isinstance(self._fieldType, GenericAlias)
            and self._fieldType.__origin__ == list
        )

    def isDict(self) -> bool:
        return (
            isinstance(self._fieldType, GenericAlias)
            and self._fieldType.__origin__ == dict
        )

    def innerType(self) -> type:
        assert self._fieldType

        if self.isList():
            assert isinstance(self._fieldType, GenericAlias)
            return self._fieldType.__args__[0]

        if self.isDict():
            assert isinstance(self._fieldType, GenericAlias)
            return self._fieldType.__args__[1]

        return self._fieldType

    def defaultValue(self) -> Any:
        if self._fieldType is None:
            return None

        if self.default is not None:
            return self.default

        if self._fieldType == bool:
            return False
        elif self._fieldType == int:
            return 0
        elif self._fieldType == str:
            return ""
        elif self.isList():
            return []
        elif self.isDict():
            return {}
        else:
            return None

    def setDefault(self, obj: Any):
        if self._fieldName:
            setattr(obj, self._fieldName, self.defaultValue())

    def castValue(self, val: Any, subkey: Optional[str]):
        try:
            val = int(val)
        except ValueError:
            pass
        except TypeError:
            pass

        if isinstance(val, list):
            return [self.castValue(v, subkey) for v in val]

        val = self.innerType()(val)

        if self.isDict() and subkey:
            return {subkey: val}

        if self.isDict():
            return {str(val): True}

        return val

    def putValue(self, obj: Any, value: Any, subkey: Optional[str] = None):
        assert self._fieldName
        value = self.castValue(value, subkey)
        field = getattr(obj, self._fieldName)
        if isinstance(field, list):
            if isinstance(value, list):
                field.extend(value)
            else:
                field.append(value)
        elif isinstance(field, dict):
            field.update(value)
        else:
            setattr(obj, self._fieldName, value)

    def getAttr(self, obj: Any) -> Any:
        assert self._fieldName
        return getattr(obj, self._fieldName)


def arg(
    shortName: str | None = None,
    longName: str = "",
    description: str = "",
    default: Any = None,
) -> Any:
    return Field(FieldKind.FLAG, shortName, longName, description, default)


def operand(longName: str = "", description: str = "", default: Any = None) -> Any:
    return Field(FieldKind.OPERAND, None, longName, description, default)


def extra(longName: str = "", description: str = "") -> Any:
    return Field(FieldKind.EXTRA, None, longName, description)


@dt.dataclass
class Schema:
    typ: Optional[type] = None
    args: list[Field] = dt.field(default_factory=list)
    operands: list[Field] = dt.field(default_factory=list)
    extras: Optional[Field] = None

    @staticmethod
    def extract(typ: type) -> "Schema":
        s = Schema(typ)

        for f in typ.__annotations__.keys():
            field = getattr(typ, f, None)

            if field is None:
                raise ValueError(f"Field '{f}' is not defined")

            if not isinstance(field, Field):
                raise ValueError(f"Field '{f}' is not a Field")

            field.bind(typ, f)

            if field.kind == FieldKind.FLAG:
                s.args.append(field)
            elif field.kind == FieldKind.OPERAND:
                s.operands.append(field)
            elif field.kind == FieldKind.EXTRA:
                if s.extras:
                    raise ValueError("Only one extra argument is allowed")
                s.extras = field

        # now move to the base class
        for base in typ.__bases__:
            if base == object:
                continue
            baseSchema = Schema.extract(base)
            s.args.extend(baseSchema.args)
            s.operands.extend(baseSchema.operands)
            if not s.extras:
                s.extras = baseSchema.extras
            elif baseSchema.extras:
                raise ValueError("Only one extra argument is allowed")

        return s

    @staticmethod
    def extractFromCallable(fn: tp.Callable) -> Optional["Schema"]:
        typ: type | None = (
            None
            if len(fn.__annotations__) == 0
            else next(iter(fn.__annotations__.values()))
        )

        if typ is None:
            return None

        return Schema.extract(typ)

    def usage(self) -> str:
        res = ""
        for arg in self.args:
            flag = ""
            if arg.shortName:
                flag += f"-{arg.shortName}"

            if arg.longName:
                if flag:
                    flag += ", "
                flag += f"--{arg.longName}"
            res += f"[{flag}] "
        for operand in self.operands:
            res += f"<{operand.longName}> "
        if self.extras:
            res += f"[-- {self.extras.longName}]"
        return res

    def _lookupArg(self, key: str, short: bool) -> Field:
        for arg in self.args:
            if short and arg.shortName == key:
                return arg
            elif not short and arg.longName == key:
                return arg
        raise ValueError(f"Unknown argument '{key}'")

    def _setOperand(self, obj: Any, value: Any):
        if len(self.operands) == 0:
            raise ValueError(f"Unexpected operand '{value}'")

        for operand in self.operands:
            if operand.getAttr(obj) is None or operand.isList():
                operand.putValue(obj, value)
                return

    def _instanciate(self) -> Any:
        if self.typ is None:
            return None
        res = self.typ()
        for arg in self.args:
            arg.setDefault(res)

        for operand in self.operands:
            assert operand._fieldName
            if operand.isList():
                setattr(res, operand._fieldName, [])
            else:
                setattr(res, operand._fieldName, None)

        if self.extras:
            self.extras.setDefault(res)

        return res

    def parse(self, args: list[str]) -> Any:
        res = self._instanciate()
        if res is None:
            if len(args) > 0:
                raise ValueError("Unexpected arguments")
            else:
                return None

        stack = args[:]
        while len(stack) > 0:
            if stack[0] == "--":
                if not self.extras:
                    raise ValueError("Unexpected '--'")
                self.extras.putValue(res, stack[1:])
                break

            toks = parseArg(stack.pop(0))
            while len(toks) > 0:
                tok = toks.pop(0)
                if isinstance(tok, ArgumentToken):
                    arg = self._lookupArg(tok.key, tok.short)
                    if tok.short and not arg.isBool():
                        if len(stack) == 0:
                            raise ValueError(
                                f"Expected value for argument '-{arg.shortName}'"
                            )

                        arg.putValue(res, parseValue(stack.pop(0)))
                    else:
                        arg.putValue(res, tok.value, tok.subkey)
                elif isinstance(tok, OperandToken):
                    self._setOperand(res, tok.value)
                else:
                    raise ValueError(f"Unexpected token: {type(tok)}")

        return res


@dt.dataclass
class Command:
    shortName: Optional[str]
    path: list[str] = dt.field(default_factory=list)
    description: str = ""
    epilog: Optional[str] = None

    schema: Optional[Schema] = None
    callable: Optional[tp.Callable] = None
    subcommands: dict[str, "Command"] = dt.field(default_factory=dict)
    populated: bool = False

    @property
    def longName(self) -> str:
        return self.path[-1]

    def _spliceArgs(self, args: list[str]) -> tuple[list[str], list[str]]:
        rest = args[:]
        curr = []
        if len(self.subcommands) > 0:
            while len(rest) > 0 and rest[0].startswith("-") and rest[0] != "--":
                curr.append(rest.pop(0))
        else:
            curr = rest
            rest = []
        return curr, rest

    def help(self):
        vt100.title(f"{self.longName}")
        print()

        vt100.subtitle("Usage")
        print(vt100.indent(f"{' '.join(self.path)}{self.usage()}"))
        print()

        vt100.subtitle("Description")
        print(vt100.indent(self.description))
        print()

        if self.schema and any(self.schema.args):
            vt100.subtitle("Options")
            for arg in self.schema.args:
                flag = ""
                if arg.shortName:
                    flag += f"-{arg.shortName}"

                if arg.longName:
                    if flag:
                        flag += ", "
                    flag += f"--{arg.longName}"

                if arg.description:
                    flag += f" {arg.description}"

                print(vt100.indent(flag))
            print()

        if any(self.subcommands):
            vt100.subtitle("Subcommands")
            for name, sub in self.subcommands.items():
                print(
                    vt100.indent(
                        f"{vt100.GREEN}{sub.shortName or ' '}{vt100.RESET}  {name} - {sub.description}"
                    )
                )
            print()

        if self.epilog:
            print(self.epilog)
            print()

    def usage(self) -> str:
        res = " "
        if self.schema:
            res += self.schema.usage()

        if len(self.subcommands) == 1:
            res += "[subcommand] [args...]"

        elif len(self.subcommands) > 0:
            res += "{"
            first = True
            for name, cmd in self.subcommands.items():
                if not first:
                    res += "|"
                res += f"{name}"
                first = False
            res += "}"

            res += " [args...]"

        return res

    def lookupSubcommand(self, name: str) -> "Command":
        if name in self.subcommands:
            return self.subcommands[name]
        for sub in self.subcommands.values():
            if sub.shortName == name:
                return sub
        raise ValueError(f"Unknown subcommand '{name}'")

    def invoke(self, argv: list[str]):
        if self.callable:
            if self.schema:
                args = self.schema.parse(argv)
                self.callable(args)
            else:
                self.callable()

    def eval(self, args: list[str]):
        cmd = args.pop(0)
        curr, rest = self._spliceArgs(args)

        if "-h" in curr or "--help" in curr:
            if len(self.path) == 1:
                # HACK: This is a special case for the root command
                #       it need to always be run because it might
                #       load some plugins that will register subcommands
                #       that need to be displayed in the help.
                self.invoke([])
            self.help()
            return

        if "-u" in curr or "--usage" in curr:
            if len(self.path) == 1:
                # HACK: Same as the help flag, the root command needs to be
                #       always run to load plugins
                self.invoke([])
            print("Usage: " + cmd + self.usage(), end="\n\n")
            return

        try:
            self.invoke(curr)

            if self.subcommands:
                if len(rest) > 0:
                    if not self.populated:
                        raise ValueError("Expected subcommand")
                    else:
                        self.lookupSubcommand(rest[0]).eval(rest)
                else:
                    print("Usage: " + cmd + self.usage(), end="\n\n")
                    return
            elif len(rest) > 0:
                raise ValueError(f"Unknown operand '{rest[0]}'")

        except ValueError as e:
            vt100.error(str(e))
            print("Usage: " + cmd + self.usage(), end="\n\n")
            return


_root = Command(None, [const.ARGV0])


def _splitPath(path: str) -> list[str]:
    if path == "/":
        return []
    return path.split("/")


def _resolvePath(path: list[str]) -> Command:
    if path == "/":
        return _root
    cmd = _root
    visited = []
    for name in path:
        visited.append(name)
        if name not in cmd.subcommands:
            cmd.subcommands[name] = Command(None, visited)
        cmd = cmd.subcommands[name]
    return cmd


def command(shortName: Optional[str], longName: str, description: str = "") -> Callable:
    def wrap(fn: Callable):
        schema = Schema.extractFromCallable(fn)
        path = _splitPath(longName)
        cmd = _resolvePath(path)

        _logger.info(f"Registering command '{'.'.join(path)}'")
        if cmd.populated:
            raise ValueError(f"Command '{longName}' is already defined")

        cmd.shortName = shortName
        cmd.description = description
        cmd.schema = schema
        cmd.callable = fn
        cmd.populated = True
        cmd.path = [const.ARGV0] + path
        return fn

    return wrap


def usage():
    print(f"Usage: {const.ARGV0} {_root.usage()}")


def exec():
    extra = os.environ.get("CK_EXTRA_ARGS", None)
    args = [const.ARGV0] + (extra.split(" ") if extra else []) + sys.argv[1:]
    _root.eval(args)


def defaults(typ: type[utils.T]) -> utils.T:
    schema = Schema.extract(typ)
    return tp.cast(utils.T, schema._instanciate())
