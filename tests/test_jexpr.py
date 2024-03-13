from cutekit import jexpr, shell


def _sum(a, b):
    return a + b


GLOBALS = {"sum": _sum, "shell": shell}


def _expand(expr: jexpr.Jexpr) -> jexpr.Jexpr:
    return jexpr.expand(expr, globals=GLOBALS)


def test_expand_str():
    assert _expand("foo") == "foo"
    assert _expand("{1}") == "1"
    assert _expand("{1 + 2}") == "3"
    assert _expand("{sum(1, 2)}") == "3"
    assert _expand("hello{sum(1, 2)}world") == "hello3world"
    assert _expand("{shell.latest('clang')}") == shell.latest("clang")


def test_expand_list():
    assert _expand([]) == []
    assert _expand([1, 2, 3]) == [1, 2, 3]
    assert _expand(["@sum", 1, 2]) == 3
    assert _expand(["@{'s' + 'um'}", 1, 2]) == 3
