<br/>
<br/>
<br/>
<p align="center">
    <img src="logo.png" width="200" height="200">
</p>
<h1 align="center">CuteKit</h1>
<p align="center">
    The Cute build system and package manager
</p>
<br/>
<br/>
<br/>

## Table of contents

- [Table of contents](#table-of-contents)
- [Macros](#macros)
  - [`@latest`](#latest)
  - [`@uname`](#uname)
  - [`@include`](#include)
  - [`@join`](#join)
  - [`@concat`](#concat)
  - [`@exec`](#exec)
- [Manifest file format](#manifest-file-format)
  - [`id`](#id)
  - [`type`](#type)
  - [`description`](#description)
  - [`enabledIf`](#enabledif)
  - [`requires`](#requires)
  - [`provides`](#provides)
- [Target file format](#target-file-format)
  - [`id`](#id-1)
  - [`type`](#type-1)
  - [`props`](#props)
  - [`tools`](#tools)


## Macros


### `@latest`

Find the latest version of a command in the path.

```json
"cc": {
    "cmd": ["@latest", "clang"], // clang-14
/* ... */
```

### `@uname`

Query the system for information about the current operating system.


```json
"cc": {
    "cmd": ["@uname", "machine"], // "x86_64"
/* ... */
```

### `@include`

Include a file

### `@join`

Join two objects

Example:

```json
["@join",  {"a": 1}, {"b": 2}] // {"a": 1, "b": 2}
```

### `@concat`

Concatenate strings

Example:

```json
["@concat", "a", "b", "c"] // "abc"
```

### `@exec`

Execute a command and return the output

Example:

```json
["@exec", "uname", "-m"] // "x86_64"
```

## Manifest file format

### `id`

The id of the package. This is used to identify the package in the manifest file.

Exemple:

```json
{
    "id": "hello"
}
```

### `type`

The type of the package. This is used to identify the package in the manifest file.

Exemple:

```json
{
    "type": "exe"
}
```

### `description`

The description of the package for the user.

Exemple:

```json
{
    "description": "Hello world"
}
```

### `enabledIf`

A list of requirements for the package check agaisnt the build props. If the requirement is not met, the package will be disabled.

```json
{
    "enabledIf": {
        "freestanding": [
            false
        ]
    }
}
```

### `requires`

Dependencies of the package. The name listed here must be the same as the id of the package or member of a provide list.

Exemple:

```json
{
    "requires": [
        "libc",
        "libm"
    ]
}
```

### `provides`

Alias for the package.

Exemple:

```json
{
    "provides": [
        "hello"
    ]
}
```


## Target file format

### `id`

The id of the target. This is used to identify the target in the target file.

### `type`

Should be `target`.

### `props`

A list of properties for the target.

Exemple:

```json
{
    "props": {
        "arch": "x86_64",
        "vendor": "pc",
        "os": "linux",
        "env": "gnu",
        "abi": "elf",
        "cpu": "x86_64",
        "features": "fxsr,sse,sse2"
    }
}
```

Theses values are exposed the translation unit as `__ck_{prop}__`.

### `tools`

A list of tools for the target.

```json
{
    "tools": {
        "cc": {
            "cmd": ["@latest", "clang"],
            "args": [
                "-target",
                "x86_64-unknown-windows",
                "-ffreestanding",
                "-fno-stack-protector",
                "-fshort-wchar",
                "-mno-red-zone"
            ]
        },
        "cxx": {
            "cmd": ["@latest", "clang++"],
            "args": [
                "-target",
                "x86_64-unknown-windows",
                "-ffreestanding",
                "-fno-stack-protector",
                "-fshort-wchar",
                "-mno-red-zone"
            ]
        },
        "ld": {
            "cmd": ["@latest", "clang++"],
            "args": [
                "-target",
                "x86_64-unknown-windows",
                "-nostdlib",
                "-Wl,-entry:efi_main",
                "-Wl,-subsystem:efi_application",
                "-fuse-ld=lld-link"
            ]
        },
        "ar": {
            "cmd": ["@latest", "llvm-ar"],
            "args": [
                "rcs"
            ]
        },
        "as": {
            "cmd": "nasm",
            "args": [
                "-f",
                "win64"
            ]
        }
    }
}
```
