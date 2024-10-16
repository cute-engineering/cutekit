#!/usr/bin/env bash

# This script is meant to be place at the root of any cutekit project.
# It will make sure that the virtual environment is set up and that the
# plugins requirements are installed.

set -e

if [ -z "$CUTEKIT_PYTHON" ]; then
    export CUTEKIT_PYTHON="python3.11"
fi

if [ -z "$CUTEKIT_VERSION" ]; then
    export CUTEKIT_VERSION="0.7.5"
fi

if [ -n "$CUTEKIT_NOVENV" ]; then
    echo "CUTEKIT_NOVENV is set, skipping virtual environment setup."
    exec cutekit $@
    exit $?
fi

if [ "$1" == "tools" -a "$2" == "nuke" ]; then
    rm -rf .cutekit/tools .cutekit/venv
    exit 0
fi

if [ ! -f .cutekit/tools/ready ]; then
    if [ ! \( "$1" == "tools" -a "$2" == "setup" \) ]; then
        echo "CuteKit is not installed."
        echo "This script will install cutekit into $PWD/.cutekit"

        read -p "Do you want to continue? [Y/n] " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "Aborting."
            exit 1
        fi
    else
        echo "Installing CuteKit..."
    fi

    mkdir -p .cutekit
    if [ ! -d .cutekit/venv ]; then
        echo "Setting up Python virtual environment..."
        $CUTEKIT_PYTHON -m venv .cutekit/venv
    fi
    source .cutekit/venv/bin/activate

    echo "Installing Tools..."
    $CUTEKIT_PYTHON -m pip install "git+https://github.com/cute-engineering/cutekit@$CUTEKIT_VERSION"

    echo "Installing plugins requirements..."
    if [ -f "meta/plugins/requirements.txt" ]; then
        echo "Root plugin requirements found."
        $CUTEKIT_PYTHON -m pip install -r meta/plugins/requirements.txt
    fi

    for extern in meta/externs/*; do
        if [ -f "$extern/meta/plugins/requirements.txt" ]; then
            echo "Plugin requirements found in $extern."
            $CUTEKIT_PYTHON -m pip install -r "$extern/meta/plugins/requirements.txt"
        fi
    done

    touch .cutekit/tools/ready
    echo "Done!"
fi

if [ "$1" == "tools" -a "$2" == "setup" ]; then
    echo "Tools already installed."
    exit 0
fi

source .cutekit/venv/bin/activate
export PATH="$PATH:.cutekit/venv/bin"

$CUTEKIT_PYTHON -m cutekit $@

