
# Extending cutekit 

By writing custom Python plugins, you can extend Cutekit to do whatever you want.

First the file need to be located in `meta/plugins` and have the `.py` extension.
Then you can import cutekit and change/add whatever you want.

For example you can add a new command to the CLI:

```python
import os
import json
import magic
import logging
from pathlib import Path


from cutekit import shell, builder, const, project
from cutekit.cmds import Cmd, append
from cutekit.args import Args
from typing import Callable


def bootCmd(args: Args) -> None:
    project.chdir()
    print("Hello world!")

append(Cmd("h", "hello", "Print hello world", bootCmd))
```

This feature is used - for example - by [SkiftOS](https://github.com/skift-org/skift/blob/main/meta/plugins/start-cmd.py) to add the `start` command, that build packages and run a virtual machine.
