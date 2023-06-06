
## Target file format

A target file is used for describing a new cross-compiler to use.
Generally, a target file is named like this: `{target}-{arch}.json`. For example, you could have: 
- `host-x86-64`
- `windows-arm`
- ...

### `id`

The `id` of the target. This is used to identify the target in the target file.

### `type`

Should be `target`.

### `props`

A list of properties for the target.

Example:

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

Theses may be accessed during compilation as C-Macros: `__ck_{prop}__`.

### `tools`

A list of tools for the target.

Each tool is described like this: 

```json
"name": {
    "cmd": "",
    "args": [
        ...
    ]
}
```

Where: 
- `cmd` describe the command to run
- `arg` describes each argument to use (note: each entry of the table correspond to ONE argument).

You have different tools names that you can use: 
- "cc"
- "cxx"
- "ld"
- "ar"
- "as"

**Example**:

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
