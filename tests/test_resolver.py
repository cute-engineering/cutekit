from cutekit import model


def test_direct_deps():
    r = model.Registry("")
    r._append(model.Component("myapp", requires=["mylib"]))
    r._append(model.Component("mylib"))
    t = model.Target("host")
    res = model.Resolver(r, t)

    resolved = res.resolve("myapp")
    assert resolved.reason is None
    assert resolved.resolved == ["myapp", "mylib"]


def test_indirect_deps():
    r = model.Registry("")
    r._append(model.Component("myapp", requires=["mylib"]))
    r._append(model.Component("mylib", requires=["myembed"]))
    r._append(model.Component("myimpl", provides=["myembed"]))
    t = model.Target("host")
    res = model.Resolver(r, t)
    assert res.resolve("myapp").resolved == ["myapp", "mylib", "myimpl"]


def test_deps_routing():
    r = model.Registry("")
    r._append(model.Component("myapp", requires=["mylib"]))
    r._append(model.Component("mylib", requires=["myembed"]))
    r._append(model.Component("myimplA", provides=["myembed"]))
    r._append(model.Component("myimplB", provides=["myembed"]))
    t = model.Target("host", routing={"myembed": "myimplB"})
    res = model.Resolver(r, t)
    assert res.resolve("myapp").resolved == ["myapp", "mylib", "myimplB"]

    t = model.Target("host", routing={"myembed": "myimplA"})
    res = model.Resolver(r, t)
    assert res.resolve("myapp").resolved == ["myapp", "mylib", "myimplA"]

    t = model.Target("host", routing={"myembed": "myimplC"})
    res = model.Resolver(r, t)
    assert res.resolve("myapp").reason == "No provider for 'myembed'"


def test_deps_routing_with_props():
    r = model.Registry("")
    r._append(model.Component("myapp", requires=["mylib"]))
    r._append(model.Component("mylib", requires=["myembed"]))
    r._append(
        model.Component("myimplA", provides=["myembed"], enableIf={"myprop": ["a"]})
    )
    r._append(
        model.Component("myimplB", provides=["myembed"], enableIf={"myprop": ["b"]})
    )
    t = model.Target("host", routing={"myembed": "myimplB"}, props={"myprop": "b"})
    res = model.Resolver(r, t)
    assert res.resolve("myapp").resolved == ["myapp", "mylib", "myimplB"]

    t = model.Target("host", routing={"myembed": "myimplA"}, props={"myprop": "a"})
    res = model.Resolver(r, t)
    assert res.resolve("myapp").resolved == ["myapp", "mylib", "myimplA"]

    t = model.Target("host", routing={"myembed": "myimplC"}, props={"myprop": "c"})
    res = model.Resolver(r, t)

    resolved = res.resolve("myapp")
    assert resolved.reason == "No provider for 'myembed'"


def test_deps_routing_with_props_and_requires():
    r = model.Registry("")
    r._append(model.Component("myapp", requires=["mylib"]))
    r._append(model.Component("mylib", requires=["myembed"]))
    r._append(
        model.Component("myimplA", provides=["myembed"], enableIf={"myprop": ["a"]})
    )
    r._append(
        model.Component("myimplB", provides=["myembed"], enableIf={"myprop": ["b"]})
    )
    t = model.Target("host", routing={"myembed": "myimplB"}, props={"myprop": "b"})
    res = model.Resolver(r, t)
    assert res.resolve("myapp").resolved == ["myapp", "mylib", "myimplB"]

    t = model.Target("host", routing={"myembed": "myimplA"}, props={"myprop": "a"})
    res = model.Resolver(r, t)
    assert res.resolve("myapp").resolved == ["myapp", "mylib", "myimplA"]

    t = model.Target("host", routing={"myembed": "myimplC"}, props={"myprop": "c"})
    res = model.Resolver(r, t)
    assert res.resolve("myapp").reason == "No provider for 'myembed'"
