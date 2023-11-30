#!/bin/env bash

set -e

export PY=python3.11

if [ ! -d "/tools/venv" ]; then
    echo "Creating virtual environment..."

    $PY -m venv /tools/venv
    source /tools/venv/bin/activate
    $PY -m ensurepip
    $PY -m pip install -r /tools/cutekit/requirements.txt
    echo "Virtual environment created."
else
    source /tools/venv/bin/activate
fi

export PYTHONPATH=/tools
$PY -m cutekit "$@"
