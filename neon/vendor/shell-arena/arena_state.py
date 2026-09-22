#!/usr/bin/env python3
"""Small, local-only, transactional counter store. Never stores command text."""
import argparse
import os
from pathlib import Path
import sqlite3


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("read", "award", "set"))
    parser.add_argument("key", nargs="?", choices=("muted", "enabled", "hud", "vibe", "volume"))
    parser.add_argument("value", nargs="?", type=int)
    args = parser.parse_args()
    os.umask(0o077)
    if args.action == "set" and (args.key is None or args.value is None):
        parser.error("set requires KEY and VALUE")
    if args.action == "set":
        limit = {"muted": 1, "enabled": 1, "hud": 1, "vibe": 2, "volume": 100}[args.key]
        if not 0 <= args.value <= limit:
            parser.error(f"{args.key} must be between 0 and {limit}")
    if args.action != "set" and (args.key is not None or args.value is not None):
        parser.error("only set accepts KEY and VALUE")
    base = Path(os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local/state"))
    folder = base / "shell-arena"
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    with sqlite3.connect(folder / "stats.sqlite3", timeout=3) as db:
        db.execute("CREATE TABLE IF NOT EXISTS counters (key TEXT PRIMARY KEY, value INTEGER NOT NULL)")
        for key, val in (("xp", 0), ("wins", 0), ("muted", 0), ("enabled", 1), ("hud", 1),
                         ("vibe", 1), ("volume", 60)):
            db.execute("INSERT OR IGNORE INTO counters VALUES (?, ?)", (key, val))
        # Validate before arithmetic too: SQLite can otherwise coerce corrupt text
        # such as '10oops' into a number while applying an award.
        ordered = validated_values(db)
        if args.action == "award":
            db.execute("UPDATE counters SET value=value+100 WHERE key='xp'")
            db.execute("UPDATE counters SET value=value+1 WHERE key='wins'")
        elif args.action == "set":
            db.execute("UPDATE counters SET value=? WHERE key=?", (int(args.value), args.key))
        ordered = validated_values(db)
    # Do not report success until the context manager has committed the write.
    print(*ordered)


def validated_values(db):
    values = dict(db.execute("SELECT key,value FROM counters"))
    ordered = [values[k] for k in ("xp", "wins", "muted", "enabled", "hud", "vibe", "volume")]
    if any(type(v) is not int or not 0 <= v <= 1000000000 for v in ordered):
        raise ValueError("Invalid local counter values; existing data was not reset.")
    if any(v not in (0, 1) for v in ordered[2:5]) or not 0 <= ordered[5] <= 2 or not 0 <= ordered[6] <= 100:
        raise ValueError("Invalid local preferences; existing data was not reset.")
    return ordered


if __name__ == "__main__":
    main()
