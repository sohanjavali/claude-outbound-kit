#!/usr/bin/env python3
"""CRM updates waiting to be applied (state/crm-pending.jsonl). Scheduled runs can't stop to approve a
CRM write, so they queue each update here, and the human applies them later by saying "sync my CRM".
Append-only: applying or skipping an update adds a line, nothing is edited or deleted.

Usage:
  python3 crm_queue.py add '{"action": "send", "email": "...", "ref": "<queue id>", "do": "..."}'   # or stdin
  python3 crm_queue.py pending [--count]         # waiting updates, oldest first
  python3 crm_queue.py done UPDATE_ID            # applied in the CRM
  python3 crm_queue.py skip UPDATE_ID "reason"   # the human decided not to apply it

Update fields:
  action   send | reply | bounce | stop | task
  email    the lead the update is about
  ref      what it came from (queue id, message_id): the same action and ref is only queued once
  do       plain words for what to change, following company/crm.md
  also     name, company, title, linkedin, category, subject, body, thread_id, message_id,
           next_task_due (YYYY-MM-DD; next_task_date and due are accepted and renamed), next_task_name, source
"""

import argparse
import datetime
import sys

from _common import STATE, append_jsonl, die, emit, locked, now, read_json_input, read_jsonl

PENDING = STATE / "crm-pending.jsonl"
ACTIONS = {"send", "reply", "bounce", "stop", "task"}
# Names a run might use for the task date, all stored as next_task_due.
DUE_ALIASES = ("next_task_date", "task_due", "task_date", "due")


def state(rows):
    """Updates in order, each with its status: pending, done or skipped."""
    updates, closed = {}, {}
    for r in rows:
        if r.get("event") == "update":
            updates.setdefault(r["id"], r)
        elif r.get("event") in ("done", "skipped") and r.get("id"):
            closed.setdefault(r["id"], r["event"])
    return [dict(u, status=closed.get(uid, "pending")) for uid, u in updates.items()]


def add(entry):
    action, email = entry.get("action"), (entry.get("email") or "").strip().lower()
    if action not in ACTIONS:
        die(f"action must be one of {sorted(ACTIONS)}")
    if not email:
        die("update is missing email")
    if not entry.get("do"):
        die("update is missing do (what to change in the CRM)")
    entry = {k: v for k, v in entry.items() if k not in ("event", "id", "at", "status")}
    entry["email"] = email
    for alias in DUE_ALIASES:
        if alias in entry:
            entry.setdefault("next_task_due", entry.pop(alias))
    due = entry.get("next_task_due")
    if due:
        try:
            datetime.date.fromisoformat(str(due)[:10])
        except ValueError:
            die(f"next_task_due must be a date like 2026-10-29, got {due!r}")
        entry["next_task_due"] = str(due)[:10]
    with locked():
        rows = read_jsonl(PENDING)
        ref = entry.get("ref")
        if ref:
            for u in state(rows):
                if u.get("action") == action and u.get("ref") == ref and u["email"] == email:
                    return {"duplicate": True, "existing": u}
        uid = f"crm-{sum(1 for r in rows if r.get('event') == 'update') + 1:05d}"
        row = {"event": "update", "id": uid, "at": now(), **entry}
        append_jsonl(PENDING, row)
    return row


def close(uid, event, reason=None):
    with locked():
        current = {u["id"]: u for u in state(read_jsonl(PENDING))}
        if uid not in current:
            die(f"no CRM update {uid}")
        if current[uid]["status"] != "pending":
            return {"id": uid, "already": current[uid]["status"]}
        row = {"event": event, "id": uid, "at": now()}
        if reason:
            row["reason"] = reason
        append_jsonl(PENDING, row)
    return row


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("add").add_argument("json", nargs="?")
    sub.add_parser("pending").add_argument("--count", action="store_true")
    sub.add_parser("done").add_argument("update_id")
    p = sub.add_parser("skip")
    p.add_argument("update_id")
    p.add_argument("reason")
    args = ap.parse_args()

    if args.cmd == "add":
        entry = read_json_input(args.json)
        if not isinstance(entry, dict):
            die("update must be a JSON object")
        emit(add(entry))
    elif args.cmd == "pending":
        waiting = [u for u in state(read_jsonl(PENDING)) if u["status"] == "pending"]
        emit({"pending": len(waiting)} if args.count else waiting)
    elif args.cmd == "done":
        emit(close(args.update_id, "done"))
    elif args.cmd == "skip":
        emit(close(args.update_id, "skipped", args.reason))
    return 0


if __name__ == "__main__":
    sys.exit(main())
