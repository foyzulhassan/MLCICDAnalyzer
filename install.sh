#!/bin/bash

TOOL_DIR=$(dirname "$(readlink -f "$0")")
MODULE_DIR=$(realpath "$TOOL_DIR/.modules")
if [ ! -d "$MODULE_DIR" ]; then
    python3 -m venv $MODULE_DIR
    source $(realpath "$MODULE_DIR/bin/activate")
    pip install --no-input -r $(realpath "$TOOL_DIR/requirements.txt")
    deactivate
fi