from pathlib import Path
from cutekit import model, project, shell
from typing import Optional
from shutil import rmtree
import os
import pytest


def check_tree(manifest_cwd: Path, args: project.InitArgs):
    assert (manifest_cwd.exists())
    if args.kind == model.Kind.PROJECT:
        assert ((manifest_cwd / f"project.{args.format}").exists())
        assert ((manifest_cwd / "src").exists())
        assert (model.Project.tryLoad((manifest_cwd / "project")))
    else:
        assert ((manifest_cwd / f"manifest.{args.format}").exists())
        assert (model.Project.tryLoad((manifest_cwd / "manifest")))


def setup_args(
        name: str,
        kind: Optional[model.Kind] = None,
        format: Optional[project.Suffix] = None
) -> project.InitArgs:
    args = project.InitArgs()
    args.name = name
    args.format = format or project.Suffix.JSON
    args.kind = kind or model.Kind.PROJECT
    args.description = "(No description)"
    return args


def test_sample_project():
    args = setup_args("test_json_sample")
    cwd = Path.cwd() / "tests"
    os.chdir(cwd)
    project_cwd = cwd / args.name
    project.init_manifest(args)
    # Check the project is correctly created
    check_tree(project_cwd, args)
    os.chdir(cwd)
    # Avoid overwriting
    pytest.raises(RuntimeError, project.init_manifest, args)
    args.format = project.Suffix.TOML
    # Avoid other manifest format creation when one is used.
    pytest.raises(RuntimeError, project.init_manifest, args)
    shell.restoreCwd()
    rmtree(project_cwd)  # Remove the directories and his content


def test_complex_project():
    args = setup_args("test_complex_project")
    cwd = Path.cwd() / "tests"
    os.chdir(cwd)
    project_cwd = cwd / args.name
    project.init_manifest(args)
    # Check the project is correctly created
    check_tree(project_cwd, args)

    # Create a lib component:
    os.chdir(project_cwd)
    args = setup_args("libcomplex", model.Kind.LIB)
    libcomplex_cwd = project_cwd / "src" / args.name
    project.init_manifest(args)
    check_tree(libcomplex_cwd, args)

    pytest.raises(RuntimeError, project.init_manifest, args)

    # Try from src
    os.chdir(project_cwd / "src")
    args = setup_args("libc", model.Kind.LIB, project.Suffix.TOML)
    project.init_manifest(args)
    libc_cwd = project_cwd / "src" / args.name
    check_tree(libc_cwd, args)

    # Creating lib inside of src/libc
    os.chdir(libc_cwd)
    pytest.raises(RuntimeError, project.init_manifest, args)

    # Creating shell directory
    os.chdir(shell.mkdir("shell"))

    # Create bash component
    args = setup_args("bash", model.Kind.EXE)
    shell_cwd = Path.cwd()
    project.init_manifest(args)
    check_tree(shell_cwd / args.name, args)

    args.name = "libc"
    pytest.raises(RuntimeError, project.init_manifest, args)
    os.chdir(project_cwd)

    shell.exec(*["tree", project_cwd])

    shell.restoreCwd()
    rmtree(project_cwd)
