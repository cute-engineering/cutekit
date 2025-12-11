import io
import os
import json
from pathlib import Path
from typing import Any, Optional
import uuid
import re
from . import model, cli, vt100, jexpr, const, builder


def graph(
    registry: model.Registry,
    target: model.Target,
    scope: Optional[str] = None,
    showExe: bool = True,
    showDisabled: bool = False,
):
    from graphviz import Digraph  # type: ignore

    g = Digraph(target.id, filename="graph.gv")

    g.attr("graph", splines="ortho", rankdir="BT", ranksep="1.5")
    g.attr("node", shape="ellipse")
    g.attr(
        "graph",
        label=f"<<B>{scope or 'Full Dependency Graph'}</B><BR/>{target.id}>",
        labelloc="t",
    )

    scopeInstance = None

    if scope is not None:
        scopeInstance = registry.lookup(scope, model.Component)

    for component in registry.iter(model.Component):
        if not component.type == model.Kind.LIB and not showExe:
            continue

        if (
            scopeInstance is not None
            and component.id != scope
            and component.id not in scopeInstance.resolved[target.id].required
        ):
            continue

        if component.resolved[target.id].enabled:
            fillcolor = "lightgrey" if component.type == model.Kind.LIB else "lightblue"
            shape = "plaintext" if not scope == component.id else "box"

            descr = component.description
            descr = descr.replace("&", "&amp;")

            g.node(
                component.id,
                f"<<B>{component.id}</B><BR/>{vt100.wordwrap(descr, 40, newline='<BR/>')}>",
                shape=shape,
                style="filled",
                fillcolor=fillcolor,
            )

            for req in component.requires:
                g.edge(component.id, req)

            for req in component.provides:
                isChosen = target.routing.get(req, None) == component.id

                g.edge(
                    req,
                    component.id,
                    arrowhead="none",
                    color=("blue" if isChosen else "black"),
                )
        elif showDisabled:
            descr = component.description
            descr = descr.replace("&", "&amp;")

            g.node(
                component.id,
                f"<<B>{component.id}</B><BR/>{vt100.wordwrap(descr, 40, newline='<BR/>')}<BR/><BR/><I>{vt100.wordwrap(str(component.resolved[target.id].reason), 40, newline='<BR/>')}</I>>",
                shape="plaintext",
                style="filled",
                fontcolor="#999999",
                fillcolor="#eeeeee",
            )

            for req in component.requires:
                g.edge(component.id, req, color="#aaaaaa")

            for req in component.provides:
                g.edge(req, component.id, arrowhead="none", color="#aaaaaa")

    g.view(filename=os.path.join(target.builddir, "graph.gv"))


class GraphArgs(model.TargetArgs):
    onlyLibs: bool = cli.arg(None, "only-libs", "Show only libraries")
    showDisabled: bool = cli.arg(None, "show-disabled", "Show disabled components")
    scope: str = cli.arg(
        None, "scope", "Show only the specified component and its dependencies"
    )


def codeWorkspace(
    project: model.Project, registry: model.Registry, all: bool = False
) -> jexpr.Jexpr:
    workspace: Any = {
        "folders": [],
        "tasks": {
            "version": "2.0.0",
            "tasks": [],
        },
        "extensions": {
            "recommendations": [
                "llvm-vs-code-extensions.vscode-clangd",
            ]
        },
    }

    folders = workspace["folders"]

    def pickEmoji(proj: model.Project) -> str:
        if proj.id == project.id:
            return "🏠"
        return "📦"

    for proj in registry.iter(model.Project):
        name = proj.id

        folders.append(
            {
                "path": proj.dirname(),
                "name": f"{pickEmoji(proj)} {name}",
            }
        )

    if all:
        folders.append(
            {
                "name": "⚙️ .cutekit (project)",
                "path": const.PROJECT_CK_DIR,
            }
        )

        folders.append(
            {
                "name": "⚙️ .cutekit (global)",
                "path": const.GLOBAL_CK_DIR,
            }
        )

    folders.sort(key=lambda x: x["name"].lower())

    tasks = workspace["tasks"]["tasks"]

    for comp in registry.iter(model.Component):
        if comp.type != model.Kind.EXE:
            continue

        tasks.append(
            {
                "icon": {"id": "play", "color": "terminal.ansiBlue"},
                "label": f"Run {comp.id}",
                "type": "shell",
                "command": f"ck run --mixins=release {comp.id}",
                "problemMatcher": [],
                "detail": comp.description,
            }
        )

        tasks.append(
            {
                "icon": {"id": "debug", "color": "terminal.ansiGreen"},
                "label": f"Debug {comp.id}",
                "type": "shell",
                "command": f"ck run --mixins=release,debug --debug {comp.id}",
                "problemMatcher": [],
                "detail": comp.description,
            }
        )

    tasks.append(
        {
            "icon": {"id": "gear", "color": "terminal.ansiYellow"},
            "label": "Build Workspace",
            "type": "shell",
            "command": "cutekit build",
            "group": {
                "kind": "build",
                "isDefault": True,
            },
            "detail": "Build the entire workspace",
        }
    )

    tasks.append(
        {
            "icon": {"id": "beaker", "color": "terminal.ansiCyan"},
            "label": "Run all tests",
            "type": "shell",
            "command": "cutekit test",
            "group": {
                "kind": "build",
                "isDefault": True,
            },
            "detail": "Run all tests in the workspace",
        }
    )

    tasks.append(
        {
            "icon": {"id": "sync", "color": "terminal.ansiYellow"},
            "label": "Sync Workspace",
            "type": "shell",
            "command": "cutekit export code-workspace --write",
            "problemMatcher": [],
            "detail": "Generate a VSCode workspace file",
        }
    )

    tasks.append(
        {
            "icon": {"id": "arrow-circle-down", "color": "terminal.ansiCyan"},
            "label": "Install externs",
            "type": "shell",
            "command": "cutekit model install",
            "problemMatcher": [],
            "detail": "Install external dependencies",
        }
    )

    tasks.append(
        {
            "icon": {"id": "trash", "color": "terminal.ansiRed"},
            "label": "Clean Workspace",
            "type": "shell",
            "command": "cutekit clean",
            "problemMatcher": [],
            "detail": "Clean the workspace",
        }
    )

    tasks.append(
        {
            "icon": {"id": "trash", "color": "terminal.ansiRed"},
            "label": "Nuke Workspace",
            "type": "shell",
            "command": "cutekit nuke",
            "problemMatcher": [],
            "detail": "Nuke the workspace",
        }
    )

    return workspace


def ideaCustomTargets(args: "IdeaWorkspaceArgs", project: model.Project):
    externalTool = '<toolSet name="External Tools">'
    customTargets = '<?xml version="1.0" encoding="UTF-8"?><project version="4"><component name="CLionExternalBuildManager">'
    configurations = '<component name="RunManager">'

    baseMixins = list(args.mixins) if args.mixins else []
    baseMixins = [m for m in baseMixins if m not in ("release", "debug")]
    baseProps: dict[str, Any] = dict(args.props) if args.props else {}
    prefix = args.prefix or "/"
    if not baseProps.get("prefix"):
        baseProps["prefix"] = prefix

    componentSpec = args.component or "__main__"
    projectRoot = Path(project.dirname()).absolute()
    projectName = projectRoot.name

    def unique(seq: list[str]) -> list[str]:
        return list(dict.fromkeys(seq))

    def resolveComponent(scope: builder.TargetScope) -> model.Component:
        routed = componentSpec
        if routed in scope.target.routing:
            routed = scope.target.routing[routed]

        component = scope.registry.lookup(routed, model.Component, includeProvides=True)
        if component is None:
            raise RuntimeError(f"Component {componentSpec} not found")

        if component.type == model.Kind.LIB:
            fallback = scope.registry.lookup(
                routed + ".main", model.Component, includeProvides=True
            )
            if fallback is None:
                raise RuntimeError(f"No entry point found for {componentSpec}")
            component = fallback

        if component.type != model.Kind.EXE:
            raise RuntimeError(f"Component {component.id} is not executable")

        resolved = component.resolved[scope.target.id]
        if not resolved.enabled:
            raise RuntimeError(
                f"Component {component.id} is disabled: {resolved.reason}"
            )

        return component

    variantDefs = [
        ("Release", "--release", unique(baseMixins + ["release"]), {"release": True}),
        ("Debug", "--debug", unique(baseMixins + ["debug"]), {"debug": True}),
    ]

    for label, flag, mixins, propUpdates in variantDefs:
        props: dict[str, Any] = dict(baseProps)
        props.pop("release", None)
        props.pop("debug", None)
        props.update(propUpdates)

        registry = model.Registry.load(project, mixins, props)
        target = registry.ensure(args.target, model.Target)
        targetScope = builder.TargetScope(registry, target)
        component = resolveComponent(targetScope)
        componentScope = targetScope.openComponentScope(component)
        runPath = builder.outfile(componentScope)
        buildDir = str(Path(target.builddir).resolve())

        targetName = f"Build {component.id} ({label})"
        toolName = f"Cutekit Build {component.id} ({label})"

        commandParts = ["build"]
        if baseMixins:
            commandParts.append(f"--mixins={','.join(baseMixins)}")
        if args.props:
            for k, v in args.props.items():
                commandParts.append(f'--props:{k}="{v}"')
        if args.prefix:
            commandParts.append(f'--prefix="{args.prefix}"')
        commandParts.append(flag)
        commandParts.append(component.id)
        parameters = " ".join(commandParts)

        customTargets += f"""
<target id="{uuid.uuid4()}" name="{targetName}" defaultType="TOOL">
<configuration id="{uuid.uuid4()}" name="{targetName}">
    <build type="TOOL">
    <tool actionId="Tool_External Tools_{toolName}" />
    </build>
    <clean type="TOOL">
    <tool actionId="Tool_External Tools_Cutekit Clean" />
    </clean>
</configuration>
</target>
        """

        externalTool += f"""
    <tool name="{toolName}" showInMainMenu="false" showInEditor="false" showInProject="false" showInSearchPopup="false" disabled="false" useConsole="true" showConsoleOnStdOut="false" showConsoleOnStdErr="false" synchronizeAfterRun="true">
    <exec>
      <option name="COMMAND" value="cutekit" />
      <option name="PARAMETERS" value="{parameters}" />
      <option name="WORKING_DIRECTORY" value="{projectRoot}" />
    </exec>
  </tool>
    """

        configurations += f"""
        <configuration name="{component.id} ({label})" type="CLionExternalRunConfiguration" factoryName="Application" singleton="false" REDIRECT_INPUT="false" ELEVATE="false" USE_EXTERNAL_CONSOLE="false" EMULATE_TERMINAL="true" WORKING_DIR="file://$PROJECT_DIR$" PASS_PARENT_ENVS_2="true" PROJECT_NAME="{projectName}" TARGET_NAME="{targetName}" CONFIG_NAME="{targetName}" RUN_PATH="{runPath}">
        <envs>
            <env name="CK_BUILDDIR" value="{buildDir}" />
            <env name="CK_COMPONENT" value="{component.id}" />
        </envs>
        <method v="2">
            <option name="CLION.EXTERNAL.BUILD" enabled="true" />
        </method>
        </configuration>
        """

    externalTool += f"""
<tool name="Cutekit Clean" showInMainMenu="false" showInEditor="false" showInProject="false" showInSearchPopup="false" disabled="false" useConsole="true" showConsoleOnStdOut="false" showConsoleOnStdErr="false" synchronizeAfterRun="true">
<exec>
    <option name="COMMAND" value="cutekit" />
    <option name="PARAMETERS" value="clean" />
    <option name="WORKING_DIRECTORY" value="{project.dirname()}" />
</exec>
</tool>
    """

    configurations += "</component>"
    externalTool += "</toolSet>"
    customTargets += "</component></project>"
    return externalTool, customTargets, configurations


def patchWorkspace(workspace_path: str, new_runmanager_xml: str) -> None:
    """
    Replace the <component name="RunManager">...</component> block in a JetBrains workspace.xml
    with the provided block. Indentation/formatting is not preserved.

    Args:
        workspace_path: Path to the workspace.xml file to patch.
        new_runmanager_xml: A string containing the full replacement component, e.g.:

            <component name="RunManager">
              ...
            </component>

    Behavior:
        - Reads the file.
        - Replaces the first (and typically only) RunManager component block.
        - Writes the result back to the same file.
        - Raises RuntimeError if no RunManager component is found.
    """
    # Read file
    with io.open(workspace_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Normalize line endings to improve matching robustness
    content = content.replace("\r\n", "\n").replace("\r", "\n")
    replacement = new_runmanager_xml.replace("\r\n", "\n").replace("\r", "\n").strip()

    # Regex to capture exactly the RunManager component block (non-greedy, dot matches newlines)
    pattern = re.compile(
        r'<component\s+name="RunManager".*?>.*?</component>',
        flags=re.DOTALL | re.IGNORECASE,
    )

    # Verify we have a match
    if not pattern.search(content):
        raise RuntimeError(
            'No <component name="RunManager">...</component> block found in the file.'
        )

    # Do the replacement
    patched = pattern.sub(replacement, content, count=1)

    # Write back
    with io.open(workspace_path, "w", encoding="utf-8") as f:
        f.write(patched)


@cli.command("export", "Export various artifacts")
def _():
    pass


@cli.command("export/graph", "Show the dependency graph")
def _(args: GraphArgs):
    registry = model.Registry.use(args)
    target = model.Target.use(args)

    graph(
        registry,
        target,
        scope=args.scope,
        showExe=not args.onlyLibs,
        showDisabled=args.showDisabled,
    )


class WorkspaceArgs(model.RegistryArgs):
    open: bool = cli.arg(None, "open", "Open the workspace file in VSCode")
    write: bool = cli.arg(None, "write", "Write the workspace file to disk")
    all: bool = cli.arg(
        None, "all", "Also include the CuteKit project and global directories"
    )


class IdeaWorkspaceArgs(model.TargetArgs):
    component: str = cli.operand(
        "component",
        "Component to generate CLion configurations for",
        default="__main__",
    )


@cli.command("export/code-workspace", "Generate a VSCode workspace file")
def _(args: WorkspaceArgs):
    project = model.Project.use()
    projectName = project.id.split("/")[-1].lower()
    registry = model.Registry.use(args)
    j = codeWorkspace(project, registry, args.all)

    args.write = args.write or args.open

    if args.write:
        with open(f"{projectName}.code-workspace", "w") as f:
            f.write(json.dumps(j, indent=2))

        print(f"Wrote {projectName}.code-workspace")
    else:
        print(json.dumps(j, indent=2))

    if args.open:
        os.system(f"code {projectName}.code-workspace")


@cli.command("export/idea-workspace", "Generate a Idea workspace file")
def _(args: IdeaWorkspaceArgs):
    project = model.Project.use()
    externalTool, customTargets, configurations = ideaCustomTargets(args, project)
    with open(".idea/tools/External Tools.xml", "w") as f:
        f.write(externalTool)

    with open(".idea/customTargets.xml", "w") as f:
        f.write(customTargets)

    patchWorkspace(".idea/workspace.xml", configurations)
