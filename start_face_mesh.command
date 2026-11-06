#!/bin/zsh
set -e

cd "${0:A:h}"

if [[ ! -x .venv/bin/python || ! -f models/face_landmarker.task ]]; then
  ./setup_python.command
fi

exec .venv/bin/python python_app/main.py "$@"
