
## Macros

To avoid headache, Cutekit extends JSON through simple macros, this is what we call **Jexpr**.


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

The `@uname` commands has 1 argument that may be: 
- `node`: to get the current machine hostname.
- `machine`: to get the current machine running architecture
  - `aarch64` is renamed to `arm64`
  - `AMD64` is renamed to `x86_64`
- `system`: to get the current machine running operating system: 
  - `Linux`
  - `Windows`
- `release`: to get the current machine operating system's version
- `version`: to get more information about the host operating system. 

### `@include`

Include a manifest file.

### `@read`

Read a Json file and output its value.

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

### `@eval`

Execute python code and return the output

Example:

```json
"32limit": ["@eval", "2**32"]
```

### `@abspath`

Returns the absolute path of a path.


