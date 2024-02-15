from cutekit import cli, utils
from asserts import (
    assert_is,
    assert_true,
    assert_equal,
    assert_raises,
    assert_is_instance,
)

# --- Parse Values ----------------------------------------------------------- #


def test_parse_int_val():
    assert_equal(cli.parseValue("1"), 1)
    assert_equal(cli.parseValue("2"), 2)
    assert_equal(cli.parseValue("+2"), +2)
    assert_equal(cli.parseValue("-2"), -2)


def test_parse_true_val():
    assert_equal(cli.parseValue("true"), True)
    assert_equal(cli.parseValue("True"), True)
    assert_equal(cli.parseValue("y"), True)
    assert_equal(cli.parseValue("yes"), True)
    assert_equal(cli.parseValue("Y"), True)
    assert_equal(cli.parseValue("Yes"), True)


def test_parse_false_val():
    assert_equal(cli.parseValue("false"), False)
    assert_equal(cli.parseValue("False"), False)
    assert_equal(cli.parseValue("n"), False)
    assert_equal(cli.parseValue("no"), False)
    assert_equal(cli.parseValue("N"), False)
    assert_equal(cli.parseValue("No"), False)


def test_parse_str_val():
    assert_equal(cli.parseValue("foo"), "foo")
    assert_equal(cli.parseValue("'foo'"), "foo")
    assert_equal(cli.parseValue('"foo"'), "foo")


def test_parse_list_val():
    assert_equal(cli.parseValue("foo,bar"), ["foo", "bar"])
    assert_equal(cli.parseValue("'foo','bar'"), ["foo", "bar"])
    assert_equal(cli.parseValue('"foo","bar"'), ["foo", "bar"])


# --- Parse Args ------------------------------------------------------------- #


def test_parse_short_arg():
    args = cli.parseArg("-a")
    assert_equal(len(args), 1)
    arg = args[0]
    assert_is_instance(arg, cli.ArgumentToken)
    assert_equal(arg.key, "a")
    assert_equal(arg.value, True)


def test_parse_short_args():
    args = cli.parseArg("-abc")
    assert_equal(len(args), 3)
    arg = args[0]
    assert_is_instance(arg, cli.ArgumentToken)
    assert_equal(arg.key, "a")
    assert_equal(arg.value, True)

    arg = args[1]
    assert_is_instance(arg, cli.ArgumentToken)
    assert_equal(arg.key, "b")
    assert_equal(arg.value, True)

    arg = args[2]
    assert_is_instance(arg, cli.ArgumentToken)
    assert_equal(arg.key, "c")
    assert_equal(arg.value, True)


def test_parse_long_arg():
    args = cli.parseArg("--foo")
    assert_equal(len(args), 1)
    arg = args[0]
    assert_is_instance(arg, cli.ArgumentToken)
    assert_equal(arg.key, "foo")
    assert_equal(arg.value, True)


def test_parse_long_arg_with_value():
    args = cli.parseArg("--foo=bar")
    assert_equal(len(args), 1)
    arg = args[0]
    assert_is_instance(arg, cli.ArgumentToken)
    assert_equal(arg.key, "foo")
    assert_equal(arg.value, "bar")


def test_parse_long_arg_with_value_list():
    args = cli.parseArg("--foo=bar,baz")
    assert_equal(len(args), 1)
    arg = args[0]
    assert_is_instance(arg, cli.ArgumentToken)
    assert_equal(arg.key, "foo")
    assert_equal(arg.value, ["bar", "baz"])


def test_parse_key_subkey_arg():
    args = cli.parseArg("--foo:bar")
    assert_equal(len(args), 1)
    arg = args[0]
    assert_is_instance(arg, cli.ArgumentToken)
    assert_equal(arg.key, "foo")
    assert_equal(arg.subkey, "bar")
    assert_equal(arg.value, True)


def extractParse(type: type[utils.T], args: list[str]) -> utils.T:
    schema = cli.Schema.extract(type)
    return schema.parse(args)


class IntArg:
    value: int = cli.arg(None, "value")


def test_cli_arg_int():

    assert_equal(extractParse(IntArg, ["--value=-1"]).value, -1)
    assert_equal(extractParse(IntArg, ["--value=0"]).value, 0)
    assert_equal(extractParse(IntArg, ["--value=1"]).value, 1)


class StrArg:
    value: str = cli.arg(None, "value")


def test_cli_arg_str1():
    assert_equal(extractParse(StrArg, ["--value=foo"]).value, "foo")
    assert_equal(extractParse(StrArg, ["--value='foo, bar'"]).value, "foo, bar")


class BoolArg:
    value: bool = cli.arg(None, "value")


def test_cli_arg_bool():
    assert_is(extractParse(BoolArg, ["--value"]).value, True)

    assert_is(extractParse(BoolArg, ["--value=true"]).value, True)
    assert_is(extractParse(BoolArg, ["--value=True"]).value, True)
    assert_is(extractParse(BoolArg, ["--value=y"]).value, True)
    assert_is(extractParse(BoolArg, ["--value=yes"]).value, True)
    assert_is(extractParse(BoolArg, ["--value=Y"]).value, True)
    assert_is(extractParse(BoolArg, ["--value=Yes"]).value, True)
    assert_is(extractParse(BoolArg, ["--value=1"]).value, True)

    assert_is(extractParse(BoolArg, ["--value=false"]).value, False)
    assert_is(extractParse(BoolArg, ["--value=False"]).value, False)
    assert_is(extractParse(BoolArg, ["--value=n"]).value, False)
    assert_is(extractParse(BoolArg, ["--value=no"]).value, False)
    assert_is(extractParse(BoolArg, ["--value=N"]).value, False)
    assert_is(extractParse(BoolArg, ["--value=No"]).value, False)
    assert_is(extractParse(BoolArg, ["--value=0"]).value, False)


class IntListArg:
    value: list[int] = cli.arg(None, "value")


def test_cli_arg_list_int1():
    assert_equal(extractParse(IntListArg, []).value, [])
    assert_equal(extractParse(IntListArg, ["--value=1", "--value=2"]).value, [1, 2])
    assert_equal(extractParse(IntListArg, ["--value=1,2"]).value, [1, 2])


class StrListArg:
    value: list[str] = cli.arg(None, "value")


def test_cli_arg_list_str():
    assert_equal(extractParse(StrListArg, []).value, [])

    assert_equal(
        extractParse(StrListArg, ["--value=foo", "--value=bar"]).value,
        [
            "foo",
            "bar",
        ],
    )

    assert_equal(extractParse(StrListArg, ["--value=foo,bar"]).value, ["foo", "bar"])
    assert_equal(extractParse(StrListArg, ["--value=foo,bar"]).value, ["foo", "bar"])
    assert_equal(extractParse(StrListArg, ["--value='foo,bar'"]).value, ["foo,bar"])
    assert_equal(extractParse(StrListArg, ["--value='foo, bar'"]).value, ["foo, bar"])
    assert_equal(extractParse(StrListArg, ['--value="foo, bar"']).value, ["foo, bar"])


class StrDictArg:
    value: dict[str, str] = cli.arg(None, "value")


def test_cli_arg_dict_str():
    assert_equal(extractParse(StrDictArg, ["--value:foo=bar"]).value, {"foo": "bar"})
    assert_equal(
        extractParse(StrDictArg, ["--value:foo=bar", "--value:baz=qux"]).value,
        {
            "foo": "bar",
            "baz": "qux",
        },
    )


class StrOptArg:
    value: str | None = cli.arg(None, "value")


def test_cli_arg_str_opt():
    assert_equal(extractParse(StrOptArg, []).value, None)
    assert_equal(extractParse(StrOptArg, ["--value=foo"]).value, "foo")


class FooArg:
    foo: str = cli.arg(None, "foo")


class BazArg:
    baz: str = cli.arg(None, "baz")


class BarArg(FooArg, BazArg):
    bar: str = cli.arg(None, "bar")


def test_cli_arg_inheritance():
    res = extractParse(BarArg, ["--foo=foo", "--bar=bar", "--baz=baz"])
    assert_equal(res.foo, "foo")
    assert_equal(res.bar, "bar")
    assert_equal(res.baz, "baz")
