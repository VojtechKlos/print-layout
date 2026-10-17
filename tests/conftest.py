import os

# Run Qt without a display (CI, tests started from a terminal).
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
