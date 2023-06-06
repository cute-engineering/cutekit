# Cutekit 

Cutekit is a build system that aims to be simple, fast and easy to use.
A project is described using json files.

## Project file 

The project file is used to describe the project and its dependencies.

See: [doc/spec/project.md](doc/spec/project.md) for the full specification.

Example: 

> project.json
```json
{
    "$schema": "https://schemas.cute.engineering/stable/cutekit.manifest.project.v1",
    "id": "skift-org/skift",
    "type": "project",
    "description": "The Skift Operating System",
    "extern": {
        "cute-engineering/libheap": {
            "git": "https://github.com/cute-engineering/libheap.git",
            "tag": "v1.1.0"
        }
    }
}
```

Here we describe a project with the id `skift-org/skift` and a dependency to `cute-engineering/libheap` at version `v1.1.0`.

## An executable package manifest


When you want to create an executable package, you need to create a `manifest.json` file in any directory under `src/`.
This is the file that describe an executable with its dependencies.

> src/nyan-cat-app/manifest.json   
```json
{
    "$schema": "https://schemas.cute.engineering/stable/cutekit.manifest.component.v1",
    "id": "nyan-cat-app",
    "type": "exe",
    "description": "rainbows everywhere",
    "requires": [
        "easy-lib"
    ]
}
```

Here we describe an executable with the id `nyan-cat-app` and a dependency to `easy-lib` (which is a library built by the project).

You can run the executable by running `$ ck run nyan-cat-app`.

## A library package manifest

When you want to create a library package, you need to create a `manifest.json` file in any directory under `src/`, like an executable package.

> src/easy-lib/manifest.json   
```json
{
    "$schema": "https://schemas.cute.engineering/stable/cutekit.manifest.component.v1",
    "id": "easy-lib",
    "type": "lib",
    "description": "easy to use library",
    "requires": [
        "cute-engineering/libheap"
    ]
}
```

Here we describe a library with the id `easy-lib` and a dependency to `cute-engineering/libheap` (which is an external dependency described above in the `project.json`).

## Using installed libraries

You can create a specific installed library through the use of `pkg-config` files.
For example here is how you add `SDL2` to your project:


> src/extern/sdl2/manifest.json
```json
{
    "$schema": "https://schemas.cute.engineering/stable/cutekit.manifest.component.v1",
    "id": "sdl2",
    "type": "lib",
    "description": "A cross-platform development library designed to provide low level access to hardware",
    "tools": {
        "cc": {
            "args": [
                "@exec",
                "pkg-config",
                "--cflags",
                "sdl2"
            ]
        },
        "cxx": {
            "args": [
                "@exec",
                "pkg-config",
                "--cflags",
                "sdl2"
            ]
        },
        "ld": {
            "args": [
                "@exec",
                "pkg-config",
                "--libs",
                "sdl2"
            ]
        }
    }
}
```
