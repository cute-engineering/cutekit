#!/bin/env bash

# This script makes sure that the virtual environment is
# set up and that the plugins requirements are installed.

set -e

export PY=python3.11

if [ ! -d "/tools/venv" ]; then
    echo "Creating virtual environment..."

    $PY -m venv /tools/venv
    source /tools/venv/bin/activate
    $PY -m ensurepip
    $PY -m pip install -r /tools/cutekit/requirements.txt

    echo "Installing plugins requirements..."
    if [ -f "/project/meta/plugins/requirements.txt" ]; then
        echo "Root plugin requirements found."
        $PY -m pip install -r /project/meta/plugins/requirements.txt
    fi

    for extern in /project/meta/externs/*; do
        if [ -f "$extern/meta/plugins/requirements.txt" ]; then
            echo "Plugin requirements found in $extern."
            $PY -m pip install -r "$extern/meta/plugins/requirements.txt"
        fi
    done

    echo "Virtual environment created."
else
    source /tools/venv/bin/activate
fi

cd /project
export PYTHONPATH=/tools
$PY -m cutekit $@
