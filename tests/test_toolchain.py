import os
from pathlib import Path

from cutekit import builder, cli, const, model, toolchain


def test_build_args_parse_toolchain():
    args = cli.Schema.extract(builder.BuildArgs).parse(
        ["--toolchain=llvm-22", "sample"]
    )

    assert args.toolchain == "llvm-22"
    assert args.component == "sample"


def test_llvm_release_resolves_partial_version(monkeypatch):
    releases = [
        {"tag_name": "llvmorg-21.1.4"},
        {"tag_name": "llvmorg-22.0.1"},
        {"tag_name": "llvmorg-22.1.3"},
        {"tag_name": "llvmorg-22.1.7"},
    ]

    monkeypatch.setattr(toolchain, "_readJson", lambda _: releases)

    assert toolchain.LlvmToolchain._release("22")["tag_name"] == "llvmorg-22.1.7"
    assert toolchain.LlvmToolchain._release("22.1")["tag_name"] == "llvmorg-22.1.7"


def test_create_llvm_aliases(tmp_path, monkeypatch):
    monkeypatch.setattr(const, "GLOBAL_TOOLCHAINS_DIR", str(tmp_path))
    tool = toolchain.LlvmToolchain("22.1.7")
    Path(tool.dir()).mkdir()

    tool._createAliases()

    assert os.readlink(tmp_path / "llvm-22") == "llvm-22.1.7"
    assert os.readlink(tmp_path / "llvm-22.1") == "llvm-22.1.7"


def test_toolchain_dir_uses_global_toolchain_root(tmp_path, monkeypatch):
    monkeypatch.setattr(const, "GLOBAL_TOOLCHAINS_DIR", str(tmp_path))

    tool = toolchain.LlvmToolchain("22")

    assert tool.dir() == str(tmp_path / "llvm-22")


def test_parse_returns_llvm_subclass():
    tool = toolchain.Toolchain.parse("llvm-22")

    assert isinstance(tool, toolchain.LlvmToolchain)


def test_parse_returns_llvm_system_subclass():
    tool = toolchain.Toolchain.parse("llvm-system")

    assert isinstance(tool, toolchain.LlvmSystemToolchain)
    assert str(tool) == "llvm-system"


def test_resolve_family_uses_selected_toolchain(tmp_path, monkeypatch):
    localCk = tmp_path / ".cutekit"
    globalCk = tmp_path / "home"
    localCk.mkdir()
    globalCk.mkdir()

    monkeypatch.setattr(const, "LOCAL_TOOLCHAIN_FILE", str(localCk / "toolchain"))
    monkeypatch.setattr(const, "GLOBAL_TOOLCHAIN_FILE", str(globalCk / "toolchain"))

    toolchain.LlvmToolchain("22").select(isGlobal=True)

    current = toolchain.Toolchain.resolve("llvm")

    assert isinstance(current, toolchain.LlvmToolchain)
    assert str(current) == "llvm-22"


def test_resolve_family_can_use_selected_llvm_system_toolchain(tmp_path, monkeypatch):
    localCk = tmp_path / ".cutekit"
    globalCk = tmp_path / "home"
    localCk.mkdir()
    globalCk.mkdir()

    monkeypatch.setattr(const, "LOCAL_TOOLCHAIN_FILE", str(localCk / "toolchain"))
    monkeypatch.setattr(const, "GLOBAL_TOOLCHAIN_FILE", str(globalCk / "toolchain"))

    toolchain.LlvmSystemToolchain("system").select(isGlobal=True)

    current = toolchain.Toolchain.resolve("llvm")

    assert isinstance(current, toolchain.LlvmSystemToolchain)
    assert str(current) == "llvm-system"


def test_resolve_explicit_llvm_system_returns_system_toolchain():
    current = toolchain.Toolchain.resolve("llvm-system")

    assert isinstance(current, toolchain.LlvmSystemToolchain)
    assert str(current) == "llvm-system"


def test_apply_llvm_toolchain_uses_alias_dir(tmp_path, monkeypatch):
    toolchains = tmp_path / "toolchains"
    monkeypatch.setattr(const, "GLOBAL_TOOLCHAINS_DIR", str(toolchains))
    bindir = toolchains / "llvm-22.1.7" / "bin"
    bindir.mkdir(parents=True)
    for toolName in ["clang", "clang++", "clang-scan-deps"]:
        path = bindir / toolName
        path.write_text("#!/bin/sh\n")
        path.chmod(0o755)

    os.symlink("llvm-22.1.7", toolchains / "llvm-22")

    target = model.Target(id="host-x86_64", props={"toolchain": "llvm-22"})
    tools = {
        "cc": model.Tool(),
        "cxx": model.Tool(),
        "ld": model.Tool(),
        "ld-shared": model.Tool(),
        "cxx-scan": model.Tool(),
    }

    toolchain.apply(target, tools)

    assert target.props["toolchain"] == "llvm"
    assert tools["cc"].cmd == str(toolchains / "llvm-22" / "bin" / "clang")
    assert tools["cxx"].cmd == str(toolchains / "llvm-22" / "bin" / "clang++")
    assert tools["ld"].cmd == str(toolchains / "llvm-22" / "bin" / "clang++")
    assert tools["ld-shared"].cmd == str(
        toolchains / "llvm-22" / "bin" / "clang++"
    )
    assert tools["cxx-scan"].cmd == str(
        toolchains / "llvm-22" / "bin" / "clang-scan-deps"
    )


def test_apply_llvm_system_toolchain_keeps_existing_tools():
    target = model.Target(id="host-x86_64", props={"toolchain": "llvm-system"})
    tools = {
        "cc": model.Tool("cc"),
        "cxx": model.Tool("c++"),
    }

    toolchain.apply(target, tools)

    assert target.props["toolchain"] == "llvm"
    assert tools["cc"].cmd == "cc"
    assert tools["cxx"].cmd == "c++"


def test_installed_lists_selectable_toolchains(tmp_path, monkeypatch):
    (tmp_path / "llvm-22.1.7").mkdir()
    os.symlink("llvm-22.1.7", tmp_path / "llvm-22")
    (tmp_path / "not-a-toolchain").mkdir()

    monkeypatch.setattr(const, "GLOBAL_TOOLCHAINS_DIR", str(tmp_path))

    assert list(map(str, toolchain.Toolchain.installed())) == [
        "llvm-22",
        "llvm-22.1.7",
    ]


def test_current_prefers_local_over_global(tmp_path, monkeypatch):
    localCk = tmp_path / ".cutekit"
    globalCk = tmp_path / "home"
    localCk.mkdir()
    globalCk.mkdir()

    monkeypatch.setattr(const, "LOCAL_TOOLCHAIN_FILE", str(localCk / "toolchain"))
    monkeypatch.setattr(const, "GLOBAL_TOOLCHAIN_FILE", str(globalCk / "toolchain"))

    toolchain.LlvmToolchain("22").select(isGlobal=True)
    toolchain.LlvmToolchain("23").select(isGlobal=False)

    current, scope = toolchain.Toolchain.current()

    assert str(current) == "llvm-23"
    assert scope == "local"


def test_current_uses_global_when_local_is_missing(tmp_path, monkeypatch):
    localCk = tmp_path / ".cutekit"
    globalCk = tmp_path / "home"
    localCk.mkdir()
    globalCk.mkdir()

    monkeypatch.setattr(const, "LOCAL_TOOLCHAIN_FILE", str(localCk / "toolchain"))
    monkeypatch.setattr(const, "GLOBAL_TOOLCHAIN_FILE", str(globalCk / "toolchain"))

    toolchain.LlvmToolchain("22").select(isGlobal=True)

    current, scope = toolchain.Toolchain.current()

    assert str(current) == "llvm-22"
    assert scope == "global"


def test_unset_local_toolchain(tmp_path, monkeypatch):
    localCk = tmp_path / ".cutekit"
    globalCk = tmp_path / "home"
    localCk.mkdir()
    globalCk.mkdir()

    monkeypatch.setattr(const, "LOCAL_TOOLCHAIN_FILE", str(localCk / "toolchain"))
    monkeypatch.setattr(const, "GLOBAL_TOOLCHAIN_FILE", str(globalCk / "toolchain"))

    toolchain.LlvmToolchain("22").select(isGlobal=False)
    toolchain.Toolchain.unset(isGlobal=False)

    current, scope = toolchain.Toolchain.current()

    assert current is None
    assert scope is None


def test_unset_all_keeps_no_selection(tmp_path, monkeypatch):
    localCk = tmp_path / ".cutekit"
    globalCk = tmp_path / "home"
    localCk.mkdir()
    globalCk.mkdir()

    monkeypatch.setattr(const, "LOCAL_TOOLCHAIN_FILE", str(localCk / "toolchain"))
    monkeypatch.setattr(const, "GLOBAL_TOOLCHAIN_FILE", str(globalCk / "toolchain"))

    toolchain.LlvmToolchain("22").select(isGlobal=False)
    toolchain.LlvmToolchain("23").select(isGlobal=True)
    toolchain.Toolchain.unset(isGlobal=False)
    toolchain.Toolchain.unset(isGlobal=True)

    current, scope = toolchain.Toolchain.current()

    assert current is None
    assert scope is None


def test_download_prints_progress(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(const, "GLOBAL_CACHE_DIR", str(tmp_path))

    def fakeUrlretrieve(url: str, path: str, reporthook):
        reporthook(1, 4, 8)
        reporthook(2, 4, 8)
        Path(path).write_bytes(b"12345678")
        return path, None

    monkeypatch.setattr(toolchain.request, "urlretrieve", fakeUrlretrieve)

    path = toolchain._download("https://example.com/LLVM.tar.xz")
    captured = capsys.readouterr()

    assert path == str(tmp_path / "LLVM.tar.xz")
    assert "Downloading LLVM.tar.xz" in captured.err
