#!/usr/bin/env bash

# This script makes sure that the virtual environment is
# set up and that the plugins requirements are installed.

set -e

if [ -z "$CUTEKIT_PYTHON" ]; then
    if command -v python3.11 &> /dev/null; then
        export CUTEKIT_PYTHON="python3.11"
    else
        export CUTEKIT_PYTHON="python3"
    fi
fi

if [ ! -d "/tools/venv" ]; then
    echo "Creating virtual environment..."

    $CUTEKIT_PYTHON -m venv /tools/venv
    source /tools/venv/bin/activate
    $CUTEKIT_PYTHON -m ensurepip
    $CUTEKIT_PYTHON -m pip install -r /tools/cutekit/requirements.txt

    echo "Installing plugins requirements..."
    if [ -f "/project/meta/plugins/requirements.txt" ]; then
        echo "Root plugin requirements found."
        $CUTEKIT_PYTHON -m pip install -r /project/meta/plugins/requirements.txt
    fi

    for extern in /project/meta/externs/*; do
        if [ -f "$extern/meta/plugins/requirements.txt" ]; then
            echo "Plugin requirements found in $extern."
            $CUTEKIT_PYTHON -m pip install -r "$extern/meta/plugins/requirements.txt"
        fi
    done

    echo "Virtual environment created."
else
    source /tools/venv/bin/activate
fi

cd /project
export PYTHONPATH=/tools
$CUTEKIT_PYTHON -m cutekit $@
