# osdk

The operating system development kit 

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

### `deps`

Dependencies of the package. The name listed here must be the same as the id of the package or member of a provide list.

Exemple:

```json
{
    "deps": [
        "libc",
        "libm"
    ]
}
```

### `provide`

Alias for the package.

Exemple:

```json
{
    "provide": [
        "hello"
    ]
}
```

### `requires`

A list of requirements for the package check agaisnt the build props. If the requirement is not met, the package will be disabled.

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

Theses values are exposed the translation unit as `__osdk_{prop}__`.

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
