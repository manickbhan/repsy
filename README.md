# Repsy

Repsy is a small, local-first workout and wellness tracker for macOS.

It has two parts:

- A macOS menu-bar app for quick logging and reminders.
- A local web dashboard for history, calendar views, and manual logging.

All data stays on the computer in `~/.repsy/` as JSON. The web server binds to
`127.0.0.1`, so it is not published to the network by default.

## Install on a Mac

Clone or download this private repository, then run the installer:

```bash
./install.sh
```

The installer creates a private virtual environment inside the repo, installs
Repsy's dependencies, and starts Repsy at login with a macOS LaunchAgent. It
never uploads your logs or connects to an AI service. Remove the app later with:

```bash
launchctl bootout "gui/$(id -u)" "$HOME/Library/LaunchAgents/com.manick.repsy.plist"
rm -f "$HOME/Library/LaunchAgents/com.manick.repsy.plist"
```

## Run it manually

Requires macOS and Python 3.12 or newer.

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

The menu-bar app starts the dashboard at <http://127.0.0.1:8842/>.

To run only the dashboard:

```bash
python web.py
```

Set `REPSY_HOME` to use another data directory. This is useful for a separate
profile or for an exported copy:

```bash
REPSY_HOME="$PWD/example-data" python web.py
```

Export and import a complete profile when moving to another Mac:

```bash
python transfer.py export ~/Desktop/repsy-profile.json
REPSY_HOME="$HOME/.repsy" python transfer.py import ~/Desktop/repsy-profile.json
```

The import replaces the current profile. Stop Repsy first and keep a backup of
`~/.repsy` before importing.

## Data and sharing

The repository contains code only. Personal logs and configuration are excluded
from git. To share Repsy, give someone access to this private repository or send
them an export of the code. Do not share `~/.repsy/log.json` unless you intend
to share the personal health and wellness data in it.

Repsy is a personal tracking tool, not medical advice. Peptide, cannabis, and
other wellness entries are private records and are not sent to a server.

## Checks

```bash
ruff check .
pytest -q
```

## License

Private project. Choose a license before making the repository public.
