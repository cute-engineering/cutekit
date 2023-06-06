
# Templates 

Templates are based on this [repository (cute-engineering/cutekit-templates)](https://github.com/cute-engineering/cutekit-templates).
Each directory correspond to a template.

You can create a new Cutekit project with the `ck I {template-name}` command.

If you want to use another repository as a template, you can use the `ck I --repo="github-link" name` command. For example: 

```bash
ck I --repo="cute-engineering/cutekit-templates.git" host
```

## Writing a template

When writing a template, you do it through a github repository (only github for now).
Then add a `registry.json` file at the root of the repository contaning a table of entry directories.

For example, if you have a UI library called `cute-ui`, you can add a `registry.json` file like this:

```json
[
    {
        "id": "cute-ui-simple",
        "description": "A simple template"
    },
    {
        "id": "cute-ui-advanced",
        "description": "A more advanced template"
    }
]
```

And each "id" will correspond to a directory in the repository:

- `cute-ui-simple` will be in `cute-ui-simple/`
- `cute-ui-advanced` will be in `cute-ui-advanced/`


