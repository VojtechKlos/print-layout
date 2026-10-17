#!/bin/sh
# Flatpak launcher: the app's code is in /app/share/printlayout, PySide6 comes from the BaseApp.
export PYTHONPATH="/app/share/printlayout${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m printlayout "$@"
