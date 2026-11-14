"""Shared helpers for the outbound-core scripts. Python 3.9+, standard library only."""

import contextlib
import datetime
import fcntl
import json
import os
import pathlib
import re
import sys
import tempfile

# The outbound-core folder. Tests point this somewhere else with OUTBOUND_CORE.
CORE = pathlib.Path(os.environ.get("OUTBOUND_CORE") or pathlib.Path(__file__).resolve().parent.parent)

STATE = CORE / "state"
LOG = STATE / "outreach-log.jsonl"
RUNS = STATE / "runs.jsonl"
QUEUE_DIR = STATE / "queue"
EXAMPLES = CORE / "person" / "examples.jsonl"

# Letters and digits in any script, joined by apostrophes, dots or hyphens ("don't", "U.S.", "co-op").
WORD_RE = re.compile(r"[^\W_]+(?:['’.\-][^\W_]+)*")
PLACEHOLDER_RE = re.compile(r"^\[.*\]$")


def load_config():
    path = CORE / "config.json"
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        die(f"config.json not found at {path}")
    except json.JSONDecodeError as e:
        die(f"config.json is not valid JSON: {e}")


_lock_depth = 0


@contextlib.contextmanager
def locked():
    """One lock for every write to state/, so overlapping runs can't interleave. Safe to nest."""
    global _lock_depth
    if _lock_depth:
        _lock_depth += 1
        try:
            yield
        finally:
            _lock_depth -= 1
        return
    STATE.mkdir(parents=True, exist_ok=True)
    with open(STATE / ".lock", "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        _lock_depth = 1
        try:
            yield
        finally:
            _lock_depth = 0
            fcntl.flock(f, fcntl.LOCK_UN)


def write_text(path, text):
    """Write atomically: a crash leaves the old file, never half a file."""
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    with os.fdopen(fd, "w") as f:
        f.write(text)
    os.replace(tmp, path)


def read_jsonl(path):
    path = pathlib.Path(path)
    if not path.exists():
        return []
    rows = []
    for n, line in enumerate(path.read_text().splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            print(f"warning: skipping bad line {n} in {path.name}", file=sys.stderr)
    return rows


def append_jsonl(path, obj):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def write_jsonl(path, rows):
    write_text(path, "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))


def read_json_input(arg=None):
    """Read JSON from a file path, a JSON string, or stdin (no arg or '-')."""
    if arg in (None, "-"):
        text = sys.stdin.read()
    elif os.path.exists(arg):
        text = pathlib.Path(arg).read_text()
    else:
        text = arg
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        die(f"input is not valid JSON: {e}")


def today():
    return datetime.date.today().isoformat()


def now():
    """Local time with its UTC offset, so times stay comparable if the laptop changes time zone."""
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def parse_dt(s):
    """Any ISO date or time (with or without an offset) as an aware local datetime. Bad input sorts first."""
    try:
        dt = datetime.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        try:
            dt = datetime.datetime.combine(datetime.date.fromisoformat(str(s)[:10]), datetime.time())
        except (TypeError, ValueError):
            dt = datetime.datetime(1970, 1, 1)
    return dt.astimezone() if dt.tzinfo else dt.replace(tzinfo=datetime.datetime.now().astimezone().tzinfo)


def parse_date(s):
    return parse_dt(s).date()


def words(text):
    return WORD_RE.findall(text or "")


def normalize(text):
    """Collapse whitespace and straighten quotes, for comparing two versions of a message."""
    text = (text or "").replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", text).strip()


def heading_key(text):
    return re.sub(r"[^a-z ]", "", normalize(text).lower().replace("cannot", "can't").replace("'", ""))


def md_bullets(path, heading):
    """Bullet items under a markdown heading, skipping [placeholders]. Matching ignores case and apostrophes."""
    path = pathlib.Path(path)
    if not path.exists():
        return []
    want = heading_key(heading)
    items, inside, level = [], False, 0
    for line in path.read_text().splitlines():
        m = re.match(r"^(#+)\s+(.*)", line)
        if m:
            if inside and len(m.group(1)) <= level:
                break
            if heading_key(m.group(2)).startswith(want):
                inside, level = True, len(m.group(1))
            continue
        if inside:
            b = re.match(r"^\s*[-*]\s+(.*)", line)
            if b:
                item = b.group(1).strip()
                if item and not PLACEHOLDER_RE.match(item) and not item.startswith("_e.g."):
                    items.append(item)
    return items


def die(msg, code=2):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


def emit(obj):
    print(json.dumps(obj, indent=2, ensure_ascii=False))
