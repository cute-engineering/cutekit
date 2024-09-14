from cutekit import cli, utils

# --- Parse Values ----------------------------------------------------------- #


def test_parse_int_val():
    assert cli.parseValue("1") == 1
    assert cli.parseValue("2") == 2
    assert cli.parseValue("+2") == +2
    assert cli.parseValue("-2") == -2


def test_parse_true_val():
    assert cli.parseValue("true") is True
    assert cli.parseValue("True") is True
    assert cli.parseValue("y") is True
    assert cli.parseValue("yes") is True
    assert cli.parseValue("Y") is True
    assert cli.parseValue("Yes") is True


def test_parse_false_val():
    assert cli.parseValue("false") is False
    assert cli.parseValue("False") is False
    assert cli.parseValue("n") is False
    assert cli.parseValue("no") is False
    assert cli.parseValue("N") is False
    assert cli.parseValue("No") is False


def test_parse_str_val():
    assert cli.parseValue("foo") == "foo"
    assert cli.parseValue("'foo'") == "foo"
    assert cli.parseValue('"foo"') == "foo"


def test_parse_list_val():
    assert cli.parseValue("foo,bar") == ["foo", "bar"]
    assert cli.parseValue("'foo','bar'") == ["foo", "bar"]
    assert cli.parseValue('"foo","bar"') == ["foo", "bar"]


# --- Parse Args ------------------------------------------------------------- #


def test_parse_short_arg():
    args = cli.parseArg("-a")
    assert len(args) == 1
    arg = args[0]
    assert isinstance(arg, cli.ArgumentToken)
    assert arg.key == "a"
    assert arg.value is True


def test_parse_short_args():
    args = cli.parseArg("-abc")
    assert len(args) == 3
    arg = args[0]
    assert isinstance(arg, cli.ArgumentToken)
    assert arg.key == "a"
    assert arg.value is True

    arg = args[1]
    assert isinstance(arg, cli.ArgumentToken)
    assert arg.key == "b"
    assert arg.value is True

    arg = args[2]
    assert isinstance(arg, cli.ArgumentToken)
    assert arg.key == "c"
    assert arg.value is True


def test_parse_long_arg():
    args = cli.parseArg("--foo")
    assert len(args) == 1
    arg = args[0]
    assert isinstance(arg, cli.ArgumentToken)
    assert arg.key == "foo"
    assert arg.value is True


def test_parse_long_arg_with_value():
    args = cli.parseArg("--foo=bar")
    assert len(args) == 1
    arg = args[0]
    assert isinstance(arg, cli.ArgumentToken)
    assert arg.key == "foo"
    assert arg.value == "bar"


def test_parse_long_arg_with_value_list():
    args = cli.parseArg("--foo=bar,baz")
    assert len(args) == 1
    arg = args[0]
    assert isinstance(arg, cli.ArgumentToken)
    assert arg.key == "foo"
    assert arg.value == ["bar", "baz"]


def test_parse_key_subkey_arg():
    args = cli.parseArg("--foo:bar")
    assert len(args) == 1
    arg = args[0]
    assert isinstance(arg, cli.ArgumentToken)
    assert arg.key == "foo"
    assert arg.subkey == "bar"
    assert arg.value is True


def extractParse(type: type[utils.T], args: list[str]) -> utils.T:
    schema = cli.Schema.extract(type)
    return schema.parse(args)


class IntArg:
    value: int = cli.arg("v", "value")


def test_cli_arg_int():
    assert extractParse(IntArg, ["-v", "-1"]).value == -1
    assert extractParse(IntArg, ["-v", "0"]).value == 0
    assert extractParse(IntArg, ["-v", "1"]).value == 1

    assert extractParse(IntArg, ["--value=-1"]).value == -1
    assert extractParse(IntArg, ["--value=0"]).value == 0
    assert extractParse(IntArg, ["--value=1"]).value == 1


class StrArg:
    value: str = cli.arg("v", "value")


def test_cli_arg_str1():
    assert extractParse(StrArg, ["--value=foo"]).value == "foo"
    assert extractParse(StrArg, ["-v", "foo"]).value == "foo"
    assert extractParse(StrArg, ["--value='foo, bar'"]).value == "foo, bar"
    assert extractParse(StrArg, ["-v", "'foo, bar'"]).value == "foo, bar"


class BoolArg:
    value: bool = cli.arg("v", "value")


def test_cli_arg_bool():
    assert extractParse(BoolArg, []).value is False

    assert extractParse(BoolArg, ["-v"]).value is True
    assert extractParse(BoolArg, ["--value"]).value is True

    assert extractParse(BoolArg, ["--value=true"]).value is True
    assert extractParse(BoolArg, ["--value=True"]).value is True
    assert extractParse(BoolArg, ["--value=y"]).value is True
    assert extractParse(BoolArg, ["--value=yes"]).value is True
    assert extractParse(BoolArg, ["--value=Y"]).value is True
    assert extractParse(BoolArg, ["--value=Yes"]).value is True
    assert extractParse(BoolArg, ["--value=1"]).value is True

    assert extractParse(BoolArg, ["--value=false"]).value is False
    assert extractParse(BoolArg, ["--value=False"]).value is False
    assert extractParse(BoolArg, ["--value=n"]).value is False
    assert extractParse(BoolArg, ["--value=no"]).value is False
    assert extractParse(BoolArg, ["--value=N"]).value is False
    assert extractParse(BoolArg, ["--value=No"]).value is False
    assert extractParse(BoolArg, ["--value=0"]).value is False


class IntListArg:
    value: list[int] = cli.arg("v", "value")


def test_cli_arg_list_int1():
    assert extractParse(IntListArg, []).value == []
    assert extractParse(IntListArg, ["--value=1", "--value=2"]).value == [1, 2]
    assert extractParse(IntListArg, ["-v", "1", "-v", "2"]).value == [1, 2]
    assert extractParse(IntListArg, ["--value=1,2"]).value == [1, 2]
    assert extractParse(IntListArg, ["-v", "1,2"]).value == [1, 2]


class StrListArg:
    value: list[str] = cli.arg("v", "value")


def test_cli_arg_list_str():
    assert extractParse(StrListArg, []).value == []

    assert extractParse(StrListArg, ["--value=foo", "--value=bar"]).value == [
        "foo",
        "bar",
    ]

    assert extractParse(StrListArg, ["--value=foo,bar"]).value == ["foo", "bar"]
    assert extractParse(StrListArg, ["--value=foo,bar"]).value == ["foo", "bar"]
    assert extractParse(StrListArg, ["--value='foo,bar'"]).value == ["foo,bar"]
    assert extractParse(StrListArg, ["--value='foo, bar'"]).value == ["foo, bar"]
    assert extractParse(StrListArg, ['--value="foo, bar"']).value == ["foo, bar"]


class StrDictArg:
    value: dict[str, str] = cli.arg(None, "value")


def test_cli_arg_dict_str():
    assert extractParse(StrDictArg, ["--value:foo=bar"]).value == {"foo": "bar"}
    assert extractParse(StrDictArg, ["--value:foo=bar", "--value:baz=qux"]).value == {
        "foo": "bar",
        "baz": "qux",
    }


class FooArg:
    foo: str = cli.arg(None, "foo")


class BazArg:
    baz: str = cli.arg(None, "baz")


class BarArg(FooArg, BazArg):
    bar: str = cli.arg(None, "bar")


def test_cli_arg_inheritance():
    res = extractParse(BarArg, ["--foo=foo", "--bar=bar", "--baz=baz"])
    assert res.foo == "foo"
    assert res.bar == "bar"
    assert res.baz == "baz"


class ExtraArg:
    value: str = cli.arg(None, "value")
    extra: list[str] = cli.extra("extra")


def test_cli_extra_args():
    res = extractParse(ExtraArg, ["--value=foo", "--", "bar", "baz"])
    assert res.value == "foo"
    assert res.extra == ["bar", "baz"]


class StrOperandArg:
    value: str = cli.operand("value")


def test_cli_operand_args():
    res = extractParse(StrOperandArg, ["foo"])
    assert res.value == "foo"


class ListOperandArg:
    value: list[str] = cli.operand("value")


def test_cli_operand_list_args():
    res = extractParse(ListOperandArg, ["foo", "bar"])
    assert res.value == ["foo", "bar"]


def test_cli_operand_list_args_empty():
    res = extractParse(ListOperandArg, [])
    assert res.value == []
