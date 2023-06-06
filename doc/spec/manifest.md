

## Manifest file format

### `id`

The `id` of the package. This is used to identify the package in the manifest file.

Example:

```json
{
    "id": "hello"
}
```

### `type`

The type of the package. This is used to identify the package in the manifest file.

Example:

```json
{
    "type": "exe"
}
```


**Values:**
- `"exe"`
- `"lib"`

### `description`

The description of the package for the user.

Example:

```json
{
    "description": "Hello world"
}
```

### `enabledIf`

A list of requirements for the package check against the build props. If the requirement is not met, the package will be disabled.

```json
{
    "enabledIf": {
        "freestanding": [
            false
        ]
    }
}
```

**Values:**

`enableIf` is a map of variable and values: 
```
"variable-name": [array of expected value] 
```
If `variable-name` is equal to one of the value in the table, then the package will be enabled.


### `requires`

Dependencies of the package. The name listed here must be the same as the `id` of the package or member of a provide list.

Example:

```json
{
    "requires": [
        "libc",
        "libm"
    ]
}
```

### `provides`

An alias for the package.

Example:

```json
{
    "provides": [
        "hello"
    ]
}
```

This alias may be used by other package when using `requires`.
This is used when you have multiple package implementing the same features, but only one is enabled through `enableIf`.

**Value**: 
- An array of `id`.