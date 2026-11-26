#!/usr/bin/env bash
set -euo pipefail

config_file="${HOME}/.config/thashu/api.env"
if [[ -r "${config_file}" ]]; then
    set -a
    # This is the user's private shell-format config, which may contain the API token.
    # shellcheck disable=SC1090
    source "${config_file}"
    set +a
fi

exec "${HOME}/.venvs/thashu/bin/python" -u main.py
