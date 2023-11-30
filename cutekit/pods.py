import sys
import docker  # type: ignore
import os
import dataclasses as dt

from . import cli, model, shell, vt100


podPrefix = "CK__"
projectRoot = "/self"
toolingRoot = "/tools"
defaultPodName = f"{podPrefix}default"
defaultPodImage = "ubuntu"


@dt.dataclass
class Image:
    id: str
    image: str
    init: list[str]


@dt.dataclass
class Pod:
    name: str
    image: Image


IMAGES: dict[str, Image] = {
    "ubuntu": Image(
        "ubuntu",
        "ubuntu:jammy",
        [
            "apt-get update",
            "apt-get install -y python3.11 python3.11-venv ninja-build",
        ],
    ),
    "debian": Image(
        "debian",
        "debian:bookworm",
        [
            "apt-get update",
            "apt-get install -y python3 python3-pip python3-venv ninja-build",
        ],
    ),
    "alpine": Image(
        "alpine",
        "alpine:3.18",
        [
            "apk update",
            "apk add python3 python3-dev py3-pip py3-venv build-base linux-headers ninja",
        ],
    ),
    "arch": Image(
        "arch",
        "archlinux:latest",
        [
            "pacman -Syu --noconfirm",
            "pacman -S --noconfirm python python-pip python-virtualenv ninja",
        ],
    ),
    "fedora": Image(
        "fedora",
        "fedora:39",
        [
            "dnf update -y",
            "dnf install -y python3 python3-pip python3-venv ninja-build",
        ],
    ),
}


def reincarnate(args: cli.Args):
    """
    Reincarnate cutekit within a docker container, this is
    useful for cross-compiling
    """
    pod = args.consumeOpt("pod", False)
    if not pod:
        return
    if isinstance(pod, str):
        pod = pod.strip()
        pod = podPrefix + pod
    if pod is True:
        pod = defaultPodName
    assert isinstance(pod, str)
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
            *args.args,
        )
        sys.exit(0)
    except Exception:
        sys.exit(1)


@cli.command("p", "pod", "Manage pods")
def podCmd(args: cli.Args):
    pass


@cli.command("c", "pod/create", "Create a new pod")
def podCreateCmd(args: cli.Args):
    """
    Create a new development pod with cutekit installed and the current
    project mounted at /self
    """
    project = model.Project.ensure()

    name = str(args.consumeOpt("name", defaultPodName))
    if not name.startswith(podPrefix):
        name = f"{podPrefix}{name}"
    image = IMAGES[str(args.consumeOpt("image", defaultPodImage))]

    client = docker.from_env()
    try:
        client.containers.get(name)
        raise RuntimeError(f"Pod '{name[len(podPrefix):]}' already exists")
    except docker.errors.NotFound:
        pass

    print(f"Staring pod '{name[len(podPrefix) :]}'...")

    container = client.containers.run(
        image.image,
        "sleep infinity",
        name=name,
        volumes={
            os.path.abspath(os.path.dirname(__file__)): {
                "bind": toolingRoot + "/cutekit",
                "mode": "ro",
            },
            os.path.abspath(project.dirname()): {"bind": projectRoot, "mode": "rw"},
        },
        detach=True,
    )

    print(f"Initializing pod '{name[len(podPrefix) :]}'...")
    for cmd in image.init:
        print(vt100.p(cmd))
        exitCode, ouput = container.exec_run(f"/bin/bash -c '{cmd}'", demux=True)
        if exitCode != 0:
            raise Exception(f"Failed to initialize pod with command '{cmd}'")

    print(f"Created pod '{name[len(podPrefix) :]}' from image '{image.image}'")


@cli.command("k", "pod/kill", "Stop and remove a pod")
def podKillCmd(args: cli.Args):
    client = docker.from_env()
    name = str(args.consumeOpt("name", defaultPodName))
    if not name.startswith(podPrefix):
        name = f"{podPrefix}{name}"

    try:
        container = client.containers.get(name)
        container.stop()
        container.remove()
        print(f"Pod '{name[len(podPrefix) :]}' killed")
    except docker.errors.NotFound:
        raise RuntimeError(f"Pod '{name[len(podPrefix):]}' does not exist")


@cli.command("s", "pod/shell", "Open a shell in a pod")
def podShellCmd(args: cli.Args):
    args.args.insert(0, "/bin/bash")
    podExecCmd(args)


@cli.command("l", "pod/list", "List all pods")
def podListCmd(args: cli.Args):
    client = docker.from_env()
    hasPods = False
    for container in client.containers.list(all=True):
        if not container.name.startswith(podPrefix):
            continue
        print(container.name[len(podPrefix) :], container.status)
        hasPods = True

    if not hasPods:
        print(vt100.p("(No pod found)"))


@cli.command("e", "pod/exec", "Execute a command in a pod")
def podExecCmd(args: cli.Args):
    name = str(args.consumeOpt("name", defaultPodName))
    if not name.startswith(podPrefix):
        name = f"{podPrefix}{name}"

    try:
        shell.exec("docker", "exec", "-it", name, *args.args)
    except Exception:
        raise RuntimeError(f"Pod '{name[len(podPrefix):]}' does not exist")
