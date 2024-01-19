import sys
from typing import Optional
import docker  # type: ignore
import os
import dataclasses as dt

from . import cli, model, shell, vt100, const


podPrefix = "CK__"
projectRoot = "/project"
toolingRoot = "/tools"
defaultPodName = f"{podPrefix}default"
defaultPodImage = "ubuntu"


@dt.dataclass
class Image:
    id: str
    like: str
    image: str
    setup: list[str]


@dt.dataclass
class Pod:
    name: str
    image: Image


IMAGES: dict[str, Image] = {
    "ubuntu": Image(
        "ubuntu",
        "ubuntu",
        "ubuntu:jammy",
        [
            "apt-get update",
            "apt-get install -y python3.11 python3.11-venv ninja-build build-essential",
        ],
    ),
    "debian": Image(
        "debian",
        "debian",
        "debian:bookworm",
        [
            "apt-get update",
            "apt-get install -y python3 python3-pip python3-venv ninja-build build-essential",
        ],
    ),
    "alpine": Image(
        "alpine",
        "alpine",
        "alpine:3.18",
        [
            "apk update",
            "apk add python3 python3-dev py3-pip py3-virtualenv build-base linux-headers ninja make automake gcc g++ bash",
        ],
    ),
    "arch": Image(
        "arch",
        "arch",
        "archlinux:latest",
        [
            "pacman -Syu --noconfirm",
            "pacman -S --noconfirm python python-pip python-virtualenv ninja base-devel",
        ],
    ),
    "fedora": Image(
        "fedora",
        "fedora",
        "fedora:39",
        [
            "dnf update -y",
            "dnf install -y python3 python3-pip python3-venv ninja-build make automake gcc gcc-c++ kernel-devel",
        ],
    ),
}


class PodArgs:
    pod = cli.Arg[bool]("p", "enable-pod", "Enable pod", default=False)
    podName = cli.Arg[str]("n", "pod-name", "The name of the pod", default="")


def setup(args: PodArgs, argv: list[str]):
    """
    Reincarnate cutekit within a docker container, this is
    useful for cross-compiling
    """
    if not args.pod:
        return

    pod = args.podName.strip() or defaultPodName
    pod = podPrefix + args.podName

    model.Project.ensure()
    print(f"Reincarnating into pod '{pod[len(podPrefix) :]}'...")
    try:
        shell.exec(
            "docker",
            "exec",
            "-w",
            projectRoot,
            "-it",
            pod,
            "/tools/cutekit/entrypoint.sh",
            "--reincarnated",
            *argv,
        )
        sys.exit(0)
    except Exception:
        sys.exit(1)


@cli.command("p", "pod", "Manage pods")
def _():
    pass


def tryDecode(data: Optional[bytes], default: str = "") -> str:
    if data is None:
        return default
    return data.decode()


class PodCreateArgs:
    name: cli.Arg[str] = cli.Arg(
        "n", "name", "The name of the pod to use", default="default"
    )
    image = cli.Arg[str]("i", "image", "The image to use", default=defaultPodImage)


@cli.command("c", "pod/create", "Create a new pod")
def _(args: PodCreateArgs):
    """
    Create a new development pod with cutekit installed and the current
    project mounted at /project
    """
    project = model.Project.ensure()

    if not args.name.startswith(podPrefix):
        name: str = f"{podPrefix}{args.name}"
    else:
        name = args.name

    image = IMAGES[args.image]

    client = docker.from_env()
    try:
        existing = client.containers.get(name)
        if cli.ask(f"Pod '{name[len(podPrefix):]}' already exists, kill it?", False):
            existing.stop()
            existing.remove()
        else:
            raise RuntimeError(f"Pod '{name[len(podPrefix):]}' already exists")
    except docker.errors.NotFound:
        pass

    print(f"Staring pod '{name[len(podPrefix) :]}'...")

    container = client.containers.run(
        image.image,
        "sleep infinity",
        name=name,
        volumes={
            const.MODULE_DIR: {
                "bind": toolingRoot + "/cutekit",
                "mode": "ro",
            },
            os.path.abspath(project.dirname()): {"bind": projectRoot, "mode": "rw"},
        },
        detach=True,
    )

    print(f"Initializing pod '{name[len(podPrefix) :]}'...")
    for cmd in image.setup:
        print(vt100.p(cmd))
        exitCode, output = container.exec_run(f"/bin/sh -c '{cmd}'", demux=True)
        if exitCode != 0:
            raise RuntimeError(
                f"Failed to initialize pod with command '{cmd}':\n\nSTDOUT:\n{vt100.indent(vt100.wordwrap(tryDecode(output[0], '<empty>')))}\nSTDERR:\n{vt100.indent(vt100.wordwrap(tryDecode(output[1], '<empty>')))}"
            )

    print(f"Created pod '{name[len(podPrefix) :]}' from image '{image.image}'")


class KillPodArgs:
    name: cli.Arg[str] = cli.Arg(
        "n", "name", "The name of the pod to kill", default=defaultPodName
    )


@cli.command("k", "pod/kill", "Stop and remove a pod")
def _(args: KillPodArgs):
    client = docker.from_env()
    if not args.name.startswith(podPrefix):
        name: str = f"{podPrefix}{args.name}"
    else:
        name = args.name

    try:
        container = client.containers.get(name)
        container.stop()
        container.remove()
        print(f"Pod '{name[len(podPrefix) :]}' killed")
    except docker.errors.NotFound:
        raise RuntimeError(f"Pod '{name[len(podPrefix):]}' does not exist")


@cli.command("l", "pod/list", "List all pods")
def _():
    client = docker.from_env()
    hasPods = False
    for container in client.containers.list(all=True):
        if not container.name.startswith(podPrefix):
            continue
        print(container.name[len(podPrefix) :], container.status)
        hasPods = True

    if not hasPods:
        print(vt100.p("(No pod found)"))


class PodExecArgs:
    name = cli.Arg("n", "name", "The name of the pod to use", default=defaultPodName)
    cmd = cli.FreeFormArg("cmd", "The command to execute", default="/bin/bash")
    args = cli.FreeFormArg("args", "The arguments to pass to the command")


@cli.command("e", "pod/exec", "Execute a command in a pod")
def podExecCmd(args: PodExecArgs):
    if not args.name.startswith(podPrefix):
        name: str = f"{podPrefix}{args.name}"
    else:
        name = args.name

    try:
        shell.exec("docker", "exec", "-it", name, args.cmd, *args.args)
    except Exception:
        raise RuntimeError(f"Pod '{name[len(podPrefix):]}' does not exist")


@cli.command("s", "pod/shell", "Open a shell in a pod")
def _(args: PodExecArgs):
    args.cmd = "/bin/bash"
    podExecCmd(args)
