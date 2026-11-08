#!/usr/bin/env bash
# Creates the isolated training environment. Safe to run more than once.
set -euo pipefail

cd "$(dirname "$0")/.."

if ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 11))'; then
  echo "Python 3.11 or newer is required as python3. Install it and run this command again." >&2
  exit 1
fi

python3 -m venv .venv

if ! .venv/bin/python -m pip install -r requirements.txt; then
  echo "Setup failed while installing packages. Check your network connection and run this command again." >&2
  exit 1
fi

echo "Setup complete. Check the environment with: .venv/bin/python -m dataset_tools.check_env"
