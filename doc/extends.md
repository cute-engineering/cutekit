# Extending cutekit

By writing custom Python plugins, you can extend Cutekit to do whatever you want.

First the file need to be located in `meta/plugins` and have the `.py` extension.
Then you can import cutekit and change/add whatever you want.

For example you can add a new command to the CLI:

```python
from cutekit import cli

@cli.command("h", "hello", "Print hello world")
def bootCmd(args: cli.Args) -> None:
    print("Hello world!")
```

This feature is used - for example - by [SkiftOS](https://github.com/skift-org/skift/blob/main/meta/plugins/start-cmd.py) to add the `start` command, that build packages and run a virtual machine.
