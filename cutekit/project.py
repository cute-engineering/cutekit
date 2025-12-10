from . import cli, model, vt100, shell
from typing import Optional
import os
from pathlib import Path
from enum import StrEnum


class Suffix(StrEnum):
    JSON = "json"
    TOML = "toml"


class InitArgs:
    name: str = cli.operand("name", "Set the name of your project")
    description: str = cli.arg(
        None, "desc", "Set the description of your project", None)
    kind: model.Kind = cli.arg(
        None, "kind", "Kind of the manifest", model.Kind.PROJECT)
    format: Suffix = cli.arg(
        None, "format", "Manifest format to use", Suffix.JSON)


def init_manifest(args: InitArgs):
    if args.name is None:
        raise RuntimeError("Your manifest should be named")

    manifest = model.Manifest(
        id=args.name,
        type=args.kind,
    )
    filename: str = "project"
    project: Optional[model.Project] = model.Project.topmost()
    schema: str = None

    """ Each type of kind """
    match model.KINDS[args.kind]:
        # Init a Component or a Target
        case model.Component | model.Target:
            if project is None:
                raise RuntimeError(
                    f"can't create '{args.kind}' without a project")

            filename = "manifest"
            if model.KINDS[args.kind] == model.Component:
                schema = model.COMPONENT_SCHEMA
                manifest = model.Component(
                    description=args.description,
                    **manifest.__dict__
                )
                if args.description:
                    manifest.description = args.description
            else:
                schema = model.TARGET_SCHEMA
                manifest = model.Target(
                    **manifest.__dict__
                )

            registry = model.Registry(project=project)
            registry._append(project)
            model.Registry._loadManifests(registry)

            if (find := registry.manifests.get(args.name)) is not None:
                raise RuntimeError(
                    f" '{args.name}' manifest already exists at `{find.path}`")

            path = Path.cwd().relative_to(
                os.path.dirname(project.path)
            )

            # If it's the root of the project
            if str(path) == project.dirname():
                os.chdir(project.subpath("src"))

            os.chdir(shell.mkdir(f"{args.name}"))

        # Init a Project.
        case model.Project:
            if project is not None:
                raise RuntimeError("can't create subproject.")

            schema = model.PROJECT_SCHEMA
            filename = "project"

            if Path.cwd().name != args.name:
                os.chdir(shell.mkdir(args.name))

            if not Path("src").exists():
                shell.mkdir("src")  # Create src subdirectories

            manifest = model.Project(
                **manifest.__dict__
            )

            if args.description:
                manifest.description = args.description

    # Avoid having manifests in different format
    if model.Manifest.tryLoad(Path.cwd() / filename):
        raise RuntimeError("Your Manifest already exist.")

    filename += f".{args.format}"
    try:
        # Filter empty variable, and protected variables from Manifest.
        manifest_data = {
            k: v for k, v in manifest.__dict__.items() if not k.startswith("_") and v
        }
        manifest_data["$schema"] = schema

        with open(filename, "w", encoding="utf-8") as f:
            match args.format:
                case Suffix.JSON:
                    import json
                    json.dump(manifest_data, f, indent=4)
                case Suffix.TOML:
                    import tomli_w
                    f.write(tomli_w.dumps(manifest_data))
    except Exception as e:
        vt100.error(f"can't create the file: {str(e.args)}")
        # Remove manifest and the directories.
        os.remove(Path.cwd() / filename)
        if (Path.cwd() / "src").exists():
            os.removedirs(Path.cwd() / "src")
        os.removedirs(Path.cwd())
    finally:
        vt100.p("Manifest created.")
    shell.restoreCwd()


@cli.command("init", "Initialize your manifest.")
def _(args: InitArgs):
    init_manifest(args)
