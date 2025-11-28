#!/usr/bin/env bash
# -*- coding: utf-8 -*-

set -euo pipefail

my_dir="$(dirname "$(realpath "$0")")"
venv_dir="${my_dir}/venv"

if [[ ! -d "${venv_dir}" ]]; then
    python3 -m venv "${venv_dir}"
    (source "${venv_dir}/bin/activate" && pip install -r "${my_dir}/requirements.txt")
fi

(source "${venv_dir}/bin/activate" && "${my_dir}/run.py" "$@")
