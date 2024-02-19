import sys
import logging
from typing import Optional
import docker  # type: ignore
import os
import dataclasses as dt

from . import cli, model, shell, vt100, const

_logger = logging.getLogger(__name__)

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
    "ubuntu-jammy": Image(
        "ubuntu-jammy",
        "ubuntu",
        "ubuntu:jammy",
        [
            "apt-get update",
            "apt-get install -y python3.11 python3.11-venv ninja-build build-essential",
        ],
    ),
    "debian-bookworm": Image(
        "debian-bookworm",
        "debian",
        "debian:bookworm",
        [
            "apt-get update",
            "apt-get install -y python3 python3-pip python3-venv ninja-build build-essential",
        ],
    ),
    "alpine-3.18": Image(
        "alpine-3.18",
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
    "fedora-39": Image(
        "fedora-39",
        "fedora",
        "fedora:39",
        [
            "dnf update -y",
            "dnf install -y python3 python3-pip ninja-build make automake gcc gcc-c++ kernel-devel",
        ],
    ),
}


class PodSetupArgs:
    pod: str | bool | None = cli.arg(
        None, "pod", "Reincarnate cutekit within the specified pod"
    )


class PodNameArg:
    name: str = cli.arg(None, "name", "Name of the pod")


class PodImageArg:
    image: str = cli.arg(None, "image", "Base image to use for the pod")


class PodCreateArgs(PodNameArg, PodImageArg):
    pass


class PodKillArgs(PodNameArg):
    all: bool = cli.arg("a", "all", "Kill all pods")


class PodExecArgs(PodNameArg):
    cmd: str = cli.operand("cmd", "Command to execute")
    args: list[str] = cli.extra("args", "Extra arguments to pass to the command")


def setup(args: PodSetupArgs):
    """
    Reincarnate cutekit within a docker container, this is
    useful for cross-compiling
    """
    if not args.pod:
        return
    _logger.info(f"Reincarnating into pod '{args.pod}'...")
    if isinstance(args.pod, str):
        pod = args.pod.strip()
        pod = podPrefix + pod
    if pod is True:
        pod = defaultPodName
    assert isinstance(pod, str)
    model.Project.ensure()
    print(f"Reincarnating into pod '{pod[len(podPrefix) :]}'...")
    try:
        strippedArgsV = list(sys.argv[1:])
        strippedArgsV = [arg for arg in strippedArgsV if not arg.startswith("--pod=")]

        shell.exec(
            "docker",
            "exec",
            "-w",
            projectRoot,
            "-i",
            pod,
            "/tools/cutekit/entrypoint.sh",
            "--reincarnated",
            *strippedArgsV,
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


@cli.command("c", "pod/create", "Create a new pod")
def _(args: PodCreateArgs):
    """
    Create a new development pod with cutekit installed and the current
    project mounted at /project
    """
    project = model.Project.ensure()

    name = args.name
    if not name.startswith(podPrefix):
        name = f"{podPrefix}{name}"
    image = IMAGES[args.image]

    client = docker.from_env()
    try:
        existing = client.containers.get(name)
        if vt100.ask(f"Pod '{name[len(podPrefix):]}' already exists, kill it?", False):
            existing.stop()
            existing.remove()
        else:
            raise RuntimeError(f"Pod '{name[len(podPrefix):]}' already exists")
    except docker.errors.NotFound:
        pass

    print(f"Starting pod '{name[len(podPrefix) :]}'...")

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


@cli.command("k", "pod/kill", "Stop and remove a pod")
def _(args: PodKillArgs):
    client = docker.from_env()

    name = args.name
    all = args.all

    if not name.startswith(podPrefix):
        name = f"{podPrefix}{name}"

    try:
        if all:
            for container in client.containers.list(all=True):
                if not container.name.startswith(podPrefix):
                    continue
                container.stop()
                container.remove()
                print(f"Pod '{args.name}' killed")
            return

        container = client.containers.get(name)
        container.stop()
        container.remove()
        print(f"Pod '{args.name}' killed")
    except docker.errors.NotFound:
        raise RuntimeError(f"Pod '{args.name}' does not exist")


@cli.command("l", "pod/list", "List all pods")
def _():
    client = docker.from_env()
    hasPods = False

    vt100.subtitle("Pods")
    for container in client.containers.list(all=True):
        if not container.name.startswith(podPrefix):
            continue
        print(container.name[len(podPrefix) :], container.status)
        hasPods = True

    if not hasPods:
        print(vt100.p("(No pod found)"))

    print()

    vt100.subtitle("Images")
    for name, image in IMAGES.items():
        print(vt100.p(f"{name}"))

    print()


@cli.command("e", "pod/exec", "Execute a command in a pod")
def podExecCmd(args: PodExecArgs):
    name = args.name

    if not name.startswith(podPrefix):
        name = f"{podPrefix}{name}"

    try:
        shell.exec("docker", "exec", "-it", name, args.cmd, *args.args)
    except Exception:
        raise RuntimeError(f"Pod '{args.name}' does not exist")
