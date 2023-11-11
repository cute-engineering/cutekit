from pathlib import Path
from typing import Any


SUPPORTED_MANIFEST = [
    "https://schemas.cute.engineering/stable/cutekit.manifest.component.v1",
    "https://schemas.cute.engineering/stable/cutekit.manifest.project.v1",
    "https://schemas.cute.engineering/stable/cutekit.manifest.target.v1",
]

OSDK_MANIFEST_NOT_SUPPORTED = (
    "OSDK manifests are not supported by CuteKit. Please use CuteKit manifest instead"
)

UNSUPORTED_MANIFEST = {
    "https://schemas.cute.engineering/stable/osdk.manifest.component.v1": OSDK_MANIFEST_NOT_SUPPORTED,
    "https://schemas.cute.engineering/stable/osdk.manifest.project.v1": OSDK_MANIFEST_NOT_SUPPORTED,
    "https://schemas.cute.engineering/stable/osdk.manifest.target.v1": OSDK_MANIFEST_NOT_SUPPORTED,
    "https://schemas.cute.engineering/latest/osdk.manifest.component": OSDK_MANIFEST_NOT_SUPPORTED,
    "https://schemas.cute.engineering/latest/osdk.manifest.project": OSDK_MANIFEST_NOT_SUPPORTED,
    "https://schemas.cute.engineering/latest/osdk.manifest.target": OSDK_MANIFEST_NOT_SUPPORTED,
}


def ensureSupportedManifest(manifest: Any, path: Path):
    if "$schema" not in manifest:
        raise RuntimeError(f"Missing $schema in {path}")

    if manifest["$schema"] in UNSUPORTED_MANIFEST:
        raise RuntimeError(
            f"Unsupported manifest schema {manifest['$schema']} in {path}: {UNSUPORTED_MANIFEST[manifest['$schema']]}"
        )

    if manifest["$schema"] not in SUPPORTED_MANIFEST:
        raise RuntimeError(
            f"Unsupported manifest schema {manifest['$schema']} in {path}"
        )
