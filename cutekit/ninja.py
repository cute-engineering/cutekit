#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


"""Python module for generating .ninja files.

Note that this is emphatically not a required piece of Ninja; it's
just a helpful utility for build-file-generation systems that already
use Python.
"""

import textwrap
from typing import TextIO, Union

from cutekit.utils import asList


def escapePath(word: str) -> str:
    return word.replace('$ ', '$$ ').replace(' ', '$ ').replace(':', '$:')


VarValue = Union[int, str, list[str], None]
VarPath = Union[str, list[str], None]


class Writer(object):
    def __init__(self, output: TextIO, width: int = 78):
        self.output = output
        self.width = width

    def newline(self) -> None:
        self.output.write('\n')

    def comment(self, text: str) -> None:
        for line in textwrap.wrap(text, self.width - 2, break_long_words=False,
                                  break_on_hyphens=False):
            self.output.write('# ' + line + '\n')

    def separator(self, text : str) -> None:
        self.output.write(f"# --- {text} ---" + '-' *
                          (self.width - 10 - len(text)) + " #\n\n")

    def variable(self, key: str, value: VarValue, indent: int = 0) -> None:
        if value is None:
            return
        if isinstance(value, list):
            value = ' '.join(filter(None, value))  # Filter out empty strings.
        self._line('%s = %s' % (key, value), indent)

    def pool(self, name: str, depth: int) -> None:
        self._line('pool %s' % name)
        self.variable('depth', depth, indent=1)

    def rule(self,
             name: str,
             command: VarValue,
             description: Union[str, None] = None,
             depfile: VarValue = None,
             generator: VarValue = False,
             pool: VarValue = None,
             restat: bool = False,
             rspfile: VarValue = None,
             rspfile_content: VarValue = None,
             deps: VarValue = None) -> None:
        self._line('rule %s' % name)
        self.variable('command', command, indent=1)
        if description:
            self.variable('description', description, indent=1)
        if depfile:
            self.variable('depfile', depfile, indent=1)
        if generator:
            self.variable('generator', '1', indent=1)
        if pool:
            self.variable('pool', pool, indent=1)
        if restat:
            self.variable('restat', '1', indent=1)
        if rspfile:
            self.variable('rspfile', rspfile, indent=1)
        if rspfile_content:
            self.variable('rspfile_content', rspfile_content, indent=1)
        if deps:
            self.variable('deps', deps, indent=1)

    def build(self,
              outputs: Union[str, list[str]],
              rule: str,
              inputs: Union[VarPath, None],
              implicit: VarPath = None,
              order_only: VarPath = None,
              variables: Union[dict[str, str], None] = None,
              implicit_outputs: VarPath = None,
              pool: Union[str, None] = None,
              dyndep: Union[str, None] = None) -> list[str]:
        outputs = asList(outputs)
        out_outputs = [escapePath(x) for x in outputs]
        all_inputs = [escapePath(x) for x in asList(inputs)]

        if implicit:
            implicit = [escapePath(x) for x in asList(implicit)]
            all_inputs.append('|')
            all_inputs.extend(implicit)
        if order_only:
            order_only = [escapePath(x) for x in asList(order_only)]
            all_inputs.append('||')
            all_inputs.extend(order_only)
        if implicit_outputs:
            implicit_outputs = [escapePath(x)
                                for x in asList(implicit_outputs)]
            out_outputs.append('|')
            out_outputs.extend(implicit_outputs)

        self._line('build %s: %s' % (' '.join(out_outputs),
                                     ' '.join([rule] + all_inputs)))
        if pool is not None:
            self._line('  pool = %s' % pool)
        if dyndep is not None:
            self._line('  dyndep = %s' % dyndep)

        if variables:
            iterator = iter(variables.items())

            for key, val in iterator:
                self.variable(key, val, indent=1)

        return outputs

    def include(self, path: str) -> None:
        self._line('include %s' % path)

    def subninja(self, path: str) -> None:
        self._line('subninja %s' % path)

    def default(self, paths: VarPath) -> None:
        self._line('default %s' % ' '.join(asList(paths)))

    def _count_dollars_before_index(self, s: str, i: int) -> int:
        """Returns the number of '$' characters right in front of s[i]."""
        dollar_count = 0
        dollar_index = i - 1
        while dollar_index > 0 and s[dollar_index] == '$':
            dollar_count += 1
            dollar_index -= 1
        return dollar_count

    def _line(self, text: str, indent: int = 0) -> None:
        """Write 'text' word-wrapped at self.width characters."""
        leading_space = '  ' * indent
        while len(leading_space) + len(text) > self.width:
            # The text is too wide; wrap if possible.

            # Find the rightmost space that would obey our width constraint and
            # that's not an escaped space.
            available_space = self.width - len(leading_space) - len(' $')
            space = available_space
            while True:
                space = text.rfind(' ', 0, space)
                if (space < 0 or
                        self._count_dollars_before_index(text, space) % 2 == 0):
                    break

            if space < 0:
                # No such space; just use the first unescaped space we can find.
                space = available_space - 1
                while True:
                    space = text.find(' ', space + 1)
                    if (space < 0 or
                            self._count_dollars_before_index(text, space) % 2 == 0):
                        break
            if space < 0:
                # Give up on breaking.
                break

            self.output.write(leading_space + text[0:space] + ' $\n')
            text = text[space+1:]

            # Subsequent lines are continuations, so indent them.
            leading_space = '  ' * (indent+2)

        self.output.write(leading_space + text + '\n')

    def close(self) -> None:
        self.output.close()


def escape(string: str) -> str:
    """Escape a string such that it can be embedded into a Ninja file without
    further interpretation."""
    assert '\n' not in string, 'Ninja syntax does not allow newlines'
    # We only have one special metacharacter: '$'.
    return string.replace('$', '$$')
