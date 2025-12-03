from . import cli, model, vt100, shell
import dataclasses, os
from pathlib import Path
from typing import Optional
from enum import StrEnum

class Suffix(StrEnum):
    JSON="json"
    TOML="toml"

class InitArgs:
    name: str = cli.operand("name", "Set the name of your project")
    description: str = cli.arg(None,"desc", "Set the description of your project", None)
    kind: model.Kind = cli.arg(None, "kind", "Kind of the manifest", model.Kind.PROJECT)
    suffix: Suffix = cli.arg(None, "prefer", "Manifest format to use", Suffix.JSON)

@cli.command("init", "Initialize your manifest.")
def init_manifest(args: InitArgs):
    if not vt100.ask(f"'{vt100.rgb(235, 111, 146) + args.name + vt100.RESET}' is the name of your project  ?"):
        return 

    filename = None
    manifest: Optional[Manifest] = None

    manifest = model.Manifest(
        id=args.name,
        type=args.kind,
    )

    """ Each type of kind """
    match model.KINDS[args.kind]:
        # Init a Component or a Target
        case model.Component | model.Target:
            filename = "manifest"
            """ Find the nearest Manifest """
            project = model.Project.topmost()
            if project is None:
                vt100.error(f"can't create '{args.kind}' without a project")
                return

            path = Path.cwd().relative_to(
                os.path.dirname(project.path)
            )

            # If it's the root of the project
            if str(path) == project.dirname():
                os.chdir(project.subpath("src"))

            # Take the manifest from above.
            while project.subpath("src") < path:
                for suffix in model.Manifest.SUFFIXES:
                    if Path(os.getcwd(), "manifest"+suffix).exists():
                        break
                path = path.parent

            os.chdir(shell.mkdir(f"{args.name}"))

            if model.KINDS[args.kind] == model.Component:
                manifest = model.Component(
                    description=args.description,
                    **manifest.__dict__
                )
                setattr(manifest, "$schema", model.SUPPORTED_MANIFEST[0])
            else:
                manifest = model.Target(
                    **manifest.__dict__
                )
                setattr(manifest, "$schema", model.SUPPORTED_MANIFEST[2])
        # Init a Project.
        case model.Project:
            if Path(os.getcwd()).name != args.name:
                os.chdir(shell.mkdir(args.name))
            filename = "project"
            if not Path("src").exists():
                shell.mkdir("src") # Create src subdirectories
            manifest = model.Project(
                **manifest.__dict__
            )
            setattr(manifest, "$schema", model.SUPPORTED_MANIFEST[1])

    if hasattr(manifest, "description") and args.description:
        manifest.description = args.description

    filename += f".{args.suffix}"
    try:
        if Path(os.getcwd(), filename).exists():
            vt100.error(f"{filename} already exist.")
            return

        manifest_data = {
            k:v for k,v in manifest.__dict__.items() if not k.startswith("_") and v
        }

        match args.suffix:
            case Suffix.JSON:
                import json
                f = open(filename, "w")
                json.dump(manifest_data, f, indent=4)
            case Suffix.TOML:
                import tomli_w
                f = open(filename, "wb")
                tomli_w.dump(manifest_data, f)
    except _:
        vt100.error("can't create the file")
    finally:
        vt100.p("Manifest created.")
