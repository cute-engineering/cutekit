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
    """
    A simple scanner for parsing command-line arguments.
    """

    _src: str
    _off: int
    _save: list[int]

    def __init__(self, src: str, off: int = 0):
        """
        Initializes a new `Scan` object.

        Args:
            src: The string to scan.
            off: The starting offset within the string.
        """
        self._src = src
        self._off = 0
        self._save = []

    def curr(self) -> str:
        """
        Returns the current character being scanned.

        Returns:
            The current character, or '\0' if at the end of the string.
        """
        if self.eof():
            return "\0"
        return self._src[self._off]

    def next(self) -> str:
        """
        Advances the scanner to the next character.

        Returns:
            The new current character, or '\0' if at the end of the string.
        """
        if self.eof():
            return "\0"

        self._off += 1
        return self.curr()

    def peek(self, off: int = 1) -> str:
        """
        Peeks at the character `off` characters ahead of the current position.

        Args:
            off: The number of characters to peek ahead.

        Returns:
            The character `off` characters ahead, or '\0' if at the end of the string.
        """
        if self._off + off >= len(self._src):
            return "\0"

        return self._src[self._off + off]

    def eof(self) -> bool:
        """
        Checks if the scanner is at the end of the string.

        Returns:
            True if at the end of the string, False otherwise.
        """
        return self._off >= len(self._src)

    def skipStr(self, s: str) -> bool:
        """
        Attempts to skip over the given string.

        Args:
            s: The string to skip.

        Returns:
            True if the string was skipped, False otherwise.
        """
        if self._src[self._off :].startswith(s):
            self._off += len(s)
            return True

        return False

    def isStr(self, s: str) -> bool:
        """
        Checks if the current position matches the given string without advancing the scanner.

        Args:
            s: The string to check.

        Returns:
            True if the string matches, False otherwise.
        """
        self.save()
        if self.skipStr(s):
            self.restore()
            return True

        self.restore()
        return False

    def save(self) -> None:
        """Saves the current scanner position."""
        self._save.append(self._off)

    def restore(self) -> None:
        """Restores the scanner position to the last saved position."""
        self._off = self._save.pop()

    def skipWhitespace(self) -> bool:
        """
        Skips over any whitespace characters.

        Returns:
            True if any whitespace was skipped, False otherwise.
        """
        result = False
        while not self.eof() and self.curr().isspace():
            self.next()
            result = True
        return result

    def skipSeparator(self, sep: str) -> bool:
        """
        Skips over the given separator string, including surrounding whitespace.

        Args:
            sep: The separator string to skip.

        Returns:
            True if the separator was skipped, False otherwise.
        """
        self.save()
        self.skipWhitespace()
        if self.skipStr(sep):
            self.skipWhitespace()
            return True

        self.restore()
        return False

    def isSeparator(self, sep: str) -> bool:
        """
        Checks if the current position matches the given separator string, including surrounding whitespace,
        without advancing the scanner.

        Args:
            sep: The separator string to check.

        Returns:
            True if the separator matches, False otherwise.
        """
        self.save()
        self.skipWhitespace()
        if self.skipStr(sep):
            self.skipWhitespace()
            self.restore()
            return True

        self.restore()
        return False

    def skipKeyword(self, keyword: str) -> bool:
        """
        Skips over the given keyword, including leading whitespace.

        Args:
            keyword: The keyword to skip.

        Returns:
            True if the keyword was skipped, False otherwise.
        """
        self.save()
        self.skipWhitespace()
        if self.skipStr(keyword) and not self.curr().isalnum():
            return True

        self.restore()
        return False

    def isKeyword(self, keyword: str) -> bool:
        """
        Checks if the current position matches the given keyword, including leading whitespace,
        without advancing the scanner.

        Args:
            keyword: The keyword to check.

        Returns:
            True if the keyword matches, False otherwise.
        """
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
    """
    Base class for command-line argument tokens.
    """

    pass


@dt.dataclass
class ArgumentToken(Token):
    """
    Represents a command-line argument token.

    Attributes:
        key: The argument key (e.g., "file" for "--file").
        subkey: An optional subkey for dictionary arguments (e.g., "name" for "--file:name").
        value: The argument value.
        short: True if the argument was specified using a short flag (e.g., "-f"), False otherwise.
    """

    key: str
    subkey: Optional[str]
    value: Value
    short: bool


@dt.dataclass
class OperandToken(Token):
    """
    Represents a command-line operand token.

    Attributes:
        value: The operand value.
    """

    value: str


@dt.dataclass
class ExtraToken(Token):
    """
    Represents extra command-line arguments after a "--" separator.

    Attributes:
        args: The list of extra arguments.
    """

    args: list[str]


def _parseIdent(s: Scan) -> str:
    """Parses an identifier from the scanner."""
    res = ""
    while not s.eof() and (s.curr().isalnum() or s.curr() in "_-+"):
        res += s.curr()
        s.next()
    return res


def _parseUntilComma(s: Scan) -> str:
    """Parses a string until a comma is encountered."""
    res = ""
    while not s.eof() and s.curr() != ",":
        res += s.curr()
        s.next()
    return res


def _expectIdent(s: Scan) -> str:
    """Parses an identifier and raises an error if not found."""
    res = _parseIdent(s)
    if len(res) == 0:
        raise RuntimeError("Expected identifier")
    return res


def _parseString(s: Scan, quote: str) -> str:
    """Parses a quoted string from the scanner."""
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
    """Tries to parse an integer, returning None if unsuccessful."""
    try:
        return int(ident)
    except ValueError:
        return None


def _parsePrimitive(s: Scan) -> PrimitiveValue:
    """Parses a primitive value from the scanner."""
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
    """Parses a command-line argument value, which can be a primitive value or a list of primitive values."""
    lhs = _parsePrimitive(s)
    if s.eof():
        return lhs
    values: List = [lhs]
    while not s.eof() and s.skipStr(","):
        values.append(_parsePrimitive(s))
    return values


def parseValue(s: str) -> Value:
    """Parses a command-line argument value from a string."""
    return _parseValue(Scan(s))


def parseArg(arg: str) -> list[Token]:
    """Parses a single command-line argument into a list of tokens."""
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
    """Parses a list of command-line arguments into a list of tokens."""
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
    """
    Enum representing the kind of command-line argument field.
    """

    FLAG = 0
    OPERAND = 1
    EXTRA = 2


@dt.dataclass
class Field:
    """
    Represents a field in a command-line argument schema.
    """

    kind: FieldKind
    shortName: Optional[str]
    longName: str
    description: str = ""
    default: Any = None

    _fieldName: str | None = dt.field(init=False, default=None)
    _fieldType: type | None = dt.field(init=False, default=None)

    def bind(self, typ: type, name: str):
        """Binds the field to a specific type and field name."""
        self._fieldName = name
        self._fieldType = typ.__annotations__[name]
        if self.longName is None:
            self.longName = name

    def isBool(self) -> bool:
        """Checks if the field is a boolean."""
        return self._fieldType is bool

    def isList(self) -> bool:
        """Checks if the field is a list."""
        return (
            isinstance(self._fieldType, GenericAlias)
            and self._fieldType.__origin__ is list
        )

    def isDict(self) -> bool:
        """Checks if the field is a dictionary."""
        return (
            isinstance(self._fieldType, GenericAlias)
            and self._fieldType.__origin__ is dict
        )

    def isUnion(self) -> bool:
        """Checks if the field is a union type."""
        return (
            isinstance(self._fieldType, tp._SpecialForm)
            and self._fieldType.__origin__ is tp.Union
        )

    def innerType(self) -> type:
        """Returns the inner type of the field (e.g., the type of elements in a list)."""
        assert self._fieldType

        if self.isList():
            assert isinstance(self._fieldType, GenericAlias)
            return self._fieldType.__args__[0]

        if self.isDict():
            assert isinstance(self._fieldType, GenericAlias)
            return self._fieldType.__args__[1]

        if self.isUnion():
            return str

        return self._fieldType

    def defaultValue(self) -> Any:
        """Returns the default value for the field."""
        if self._fieldType is None:
            return None

        if self.default is not None:
            return self.default

        if self._fieldType is bool:
            return False
        elif self._fieldType is int:
            return 0
        elif self._fieldType is str:
            return ""
        elif self.isList():
            return []
        elif self.isDict():
            return {}
        else:
            return None

    def setDefault(self, obj: Any):
        """Sets the default value for the field on the given object."""
        if self._fieldName:
            setattr(obj, self._fieldName, self.defaultValue())

    def castValue(self, val: Any, subkey: Optional[str]):
        """Casts the given value to the field's type."""
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
        """Sets the field's value on the given object."""
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
        """Gets the field's value from the given object."""
        assert self._fieldName
        return getattr(obj, self._fieldName)


def arg(
    shortName: str | None = None,
    longName: str = "",
    description: str = "",
    default: Any = None,
) -> Any:
    """
    Decorator for defining a command-line argument field.

    Args:
        shortName: The short name of the argument (e.g., "f" for "-f").
        longName: The long name of the argument (e.g., "file" for "--file").
        description: A description of the argument.
        default: The default value for the argument.
    """
    return Field(FieldKind.FLAG, shortName, longName, description, default)


def operand(longName: str = "", description: str = "", default: Any = None) -> Any:
    """
    Decorator for defining a command-line operand field.

    Args:
        longName: The name of the operand.
        description: A description of the operand.
        default: The default value for the operand.
    """
    return Field(FieldKind.OPERAND, None, longName, description, default)


def extra(longName: str = "", description: str = "") -> Any:
    """
    Decorator for defining a field for extra command-line arguments.

    Args:
        longName: The name of the extra arguments field.
        description: A description of the extra arguments field.
    """
    return Field(FieldKind.EXTRA, None, longName, description)


class HelpRequested(Exception):
    pass


class UsageRequested(Exception):
    pass


@dt.dataclass
class Schema:
    """
    Represents a command-line argument schema.
    """

    typ: Optional[type] = None
    args: list[Field] = dt.field(default_factory=list)
    operands: list[Field] = dt.field(default_factory=list)
    extras: Optional[Field] = None

    @staticmethod
    def extract(typ: type) -> "Schema":
        """Extracts a command-line argument schema from a type."""
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
            if base is object:
                continue
            baseSchema = Schema.extract(base)
            s.args.extend(baseSchema.args)
            s.operands.extend(baseSchema.operands)
            if not s.extras:
                s.extras = baseSchema.extras
            elif baseSchema.extras:
                raise ValueError("Only one extra argument is allowed")

        s.args = sorted(s.args, key=lambda f: f.longName)

        return s

    @staticmethod
    def extractFromCallable(fn: tp.Callable) -> Optional["Schema"]:
        """Extracts a command-line argument schema from a callable."""
        typ: type | None = (
            None
            if len(fn.__annotations__) == 0
            else next(iter(fn.__annotations__.values()))
        )

        if typ is None:
            return None

        return Schema.extract(typ)

    def usage(self) -> str:
        """Returns a usage string for the schema."""
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
        """Looks up an argument field by key and short flag."""
        for arg in self.args:
            if short and arg.shortName == key:
                return arg
            elif not short and arg.longName == key:
                return arg
        raise ValueError(f"Unknown argument '{key}'")

    def _setOperand(self, obj: Any, value: Any):
        """Sets the value of the next available operand field on the given object."""
        if len(self.operands) == 0:
            raise ValueError(f"Unexpected operand '{value}'")

        for operand in self.operands:
            if operand.getAttr(obj) is None or operand.isList():
                operand.putValue(obj, value)
                return

    def _instanciate(self) -> Any:
        """Instantiates an object of the schema's type with default values."""
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
        """Parses a list of arguments according to the schema."""
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
                    if tok.key == "h" or tok.key == "help":
                        raise HelpRequested()

                    if tok.key == "u" or tok.key == "usage":
                        raise UsageRequested()

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
    """
    Represents a command in the command-line interface.
    """

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
        """Returns the long name of the command."""
        return self.path[-1]

    def _spliceArgs(self, args: list[str]) -> tuple[list[str], list[str]]:
        """Splices the argument list into arguments for the current command and arguments for subcommands."""
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
        """Prints the help message for the command."""
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
        """Returns a usage string for the command."""
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
        """Looks up a subcommand by name."""
        if name in self.subcommands:
            return self.subcommands[name]
        for sub in self.subcommands.values():
            if sub.shortName == name:
                return sub
        raise ValueError(f"Unknown subcommand '{name}'")

    def invoke(self, argv: list[str]):
        """Invokes the command with the given arguments."""
        if self.callable:
            if self.schema:
                args = self.schema.parse(argv)
                self.callable(args)
            else:
                self.callable()

    def eval(self, args: list[str]):
        """Evaluates the command and its subcommands based on the given arguments."""
        cmd = args.pop(0)
        curr, rest = self._spliceArgs(args)

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

        except HelpRequested:
            if len(self.path) == 1:
                # HACK: This is a special case for the root command
                #       it need to always be run because it might
                #       load some plugins that will register subcommands
                #       that need to be displayed in the help.
                self.invoke([])

            self.help()
            return

        except UsageRequested:
            if len(self.path) == 1:
                # HACK: This is a special case for the root command
                #       it need to always be run because it might
                #       load some plugins that will register subcommands
                #       that need to be displayed in the help.
                self.invoke([])

            print("Usage: " + cmd + self.usage(), end="\n\n")
            return

        except ValueError as e:
            vt100.error(str(e))
            print("Usage: " + cmd + self.usage(), end="\n\n")
            return


_root = Command(None, [const.ARGV0])


def _splitPath(path: str) -> list[str]:
    """Splits a command path into its individual components."""
    if path == "/":
        return []
    return path.split("/")


def _resolvePath(path: list[str]) -> Command:
    """Resolves a command path to a `Command` object."""
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
    """
    Decorator for defining a command.

    Args:
        shortName: The short name of the command (e.g., "f" for "-f").
        longName: The long name of the command (e.g., "file" for "--file").
        description: A description of the command.
    """

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
    """Prints the usage message for the root command."""
    print(f"Usage: {const.ARGV0} {_root.usage()}")


def exec():
    """Executes the command-line interface."""
    extra = os.environ.get("CK_EXTRA_ARGS", None)
    args = [const.ARGV0] + (extra.split(" ") if extra else []) + sys.argv[1:]
    _root.eval(args)


def defaults(typ: type[utils.T]) -> utils.T:
    """Returns an object of the given type with default values populated according to the schema."""
    schema = Schema.extract(typ)
    return tp.cast(utils.T, schema._instanciate())
