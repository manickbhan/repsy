#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ "$(uname -s)" != "Darwin" ]; then
  printf '%s\n' 'Repsy currently requires macOS.' >&2
  exit 1
fi

PYTHON=${PYTHON:-$(command -v python3)}
if [ -z "$PYTHON" ]; then
  printf '%s\n' 'Python 3 is required. Install it from python.org or Homebrew, then run this again.' >&2
  exit 1
fi

case "$($PYTHON -c 'import sys; print(sys.version_info.major * 100 + sys.version_info.minor)')" in
  3[1-9][0-9]|4[0-9][0-9]) ;;
  *) printf '%s\n' 'Repsy requires Python 3.12 or newer.' >&2; exit 1 ;;
esac

VENV="$ROOT/.venv"
"$PYTHON" -m venv "$VENV"
"$VENV/bin/python" -m pip install --upgrade pip
"$VENV/bin/python" -m pip install -r "$ROOT/requirements.txt"
PYTHON="$VENV/bin/python" "$ROOT/packaging/install_launch_agent.sh"

printf '\nRepsy is installed and will start when you sign in.\n'
printf 'Dashboard: http://127.0.0.1:%s/\n' "$("$VENV/bin/python" -c 'import store; print(store.load_config()["port"])')"
printf 'Your private data stays in: %s\n' "$HOME/.repsy"
