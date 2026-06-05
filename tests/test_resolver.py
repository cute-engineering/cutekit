from cutekit import model


def test_direct_deps():
    r = model.Registry("")
    r._append(model.Component("myapp", requires=["mylib"]))
    r._append(model.Component("mylib"))
    t = model.Target("host")
    res = model.Resolver(r, t)

    resolved = res.resolve("myapp")
    assert resolved.reason is None
    assert resolved.required == ["myapp", "mylib"]


def test_indirect_deps():
    r = model.Registry("")
    r._append(model.Component("myapp", requires=["mylib"]))
    r._append(model.Component("mylib", requires=["myembed"]))
    r._append(model.Component("myimpl", provides=["myembed"]))
    t = model.Target("host")
    res = model.Resolver(r, t)
    assert res.resolve("myapp").required == ["myapp", "mylib", "myimpl"]
