## project.json

The project file is the main file of the project.
It describes the project and its dependencies.

### `id`

The `id` of the project. This is used to identify the project.

### `type`

Should be `project`.

### `description`

The description of the project for the user.

### `extern`

A list of external dependencies for the project, for example: 

```json

"externs": {
    "cute-engineering/libheap": {
        "git": "https://github.com/cute-engineering/libheap.git",
        "tag": "v1.1.0"
    }
}
```

You describe the project `id`, the `git` repository and the `tag` to use.

