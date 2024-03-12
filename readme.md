<br/>
<br/>
<br/>
<p align="center">
    <img src="https://branding.cute.engineering/projects/cutekit/logo.png" width="200" height="200">
</p>
<h1 align="center">CuteKit</h1>
<p align="center">
    The *magical* build system and package manager
</p>
<br/>
<br/>
<br/>

## Table of contents

- [Table of contents](#table-of-contents)
- [Introduction](#introduction)
- [Installation](#installation)
- [Quick-start](#quick-start)
- [Example](#example)
- [License](#license)


## Introduction

**CuteKit** is a simple - yet - powerful build system and package manager for C and C++. It:

- ✨ It uses **JSON**: Cutekit uses JSON instead of introducing a whole new programming language for describing the project. And also has macros to help the user experience (see [Jexpr](doc/spec/jexpr.md)).
- ✨ It's a **package manager**: Cutekit package manager is based on **Git**, nothing is centralized.
- ✨ It's **extendible**: Cutekit can be [extended](./doc/extends.md) by writing custom Python plugins.
- ✨ It's **easy**: the [**templates**](./doc/templates.md) help the user quick-start a project.
- ✨ It's **portable**: Cutekit can run on MacOS Gnu/Linux and Windows.

## Installation

To install Cutekit, you may use your favourite package manager if it is available. Or you can install it manually by following the instructions below.

```bash
$ git clone https://github.com/cute-engineering/cutekit

$ cd cutekit

# If you want to use the latest version of Cutekit, you can switch to the dev branch.
# $ git switch dev

$ pip install --user -e .
```

## Quick-start

-> If you directly want to start using Cutekit for a new project, you can just run `$ ck I host` and it will create a new project in the host directory (you can rename it later).

-> If you want to use Cutekit for writing operating systems, you can create a new [limine](https://github.com/limine-bootloader/limine/)-based project by running `$ ck I limine-barebone`.

## Example

If you want to see how it works you can read the [doc/cutekit.md](doc/cutekit.md) file.

## License

<a href="https://opensource.org/licenses/MIT">
  <img align="right" height="96" alt="MIT License" src="https://branding.cute.engineering/licenses/mit.svg" />
</a>

Cutekit is licensed under the **MIT License**.

The full text of the license can be accessed via [this link](https://opensource.org/licenses/MIT) and is also included in the [license.md](license.md) file of this software package.
