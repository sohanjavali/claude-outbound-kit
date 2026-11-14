#!/usr/bin/env python3
"""Write a file inside the kit from stdin. Claude Code protects ~/.claude/ from its own file-writing
tool, so skills write their files through this script instead.

Usage:
  python3 kit_write.py company/offer.md < text        # replace a file
  python3 kit_write.py state/reports/2026-10-20.md < text
  python3 kit_write.py config.json < json              # must be valid JSON

Only these paths are allowed: config.json, company/*.md, person/*.md, state/reports/*.md.
"""

import json
import re
import sys

from _common import CORE, die, emit, locked, write_text

ALLOWED = re.compile(r"^(config\.json|company/[\w.-]+\.md|person/[\w.-]+\.md|state/reports/[\w.-]+\.md)$")


def main():
    if len(sys.argv) != 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0 if len(sys.argv) == 2 else 2)
    rel = sys.argv[1].strip().lstrip("./")
    if not ALLOWED.match(rel):
        die(f"{rel} isn't a path skills may write (config.json, company/*.md, person/*.md, state/reports/*.md)")
    text = sys.stdin.read()
    if not text.strip():
        die("nothing on stdin; refusing to write an empty file")
    if rel == "config.json":
        try:
            json.loads(text)
        except json.JSONDecodeError as e:
            die(f"config.json would not be valid JSON: {e}")
    with locked():
        write_text(CORE / rel, text if text.endswith("\n") else text + "\n")
    emit({"written": rel, "bytes": len(text.encode())})


if __name__ == "__main__":
    main()
