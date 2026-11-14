#!/usr/bin/env python3
"""The review queue: a machine record (state/queue/DATE.jsonl) and the file the human edits
(state/queue/DATE.md). Scripts only insert new items, change one status line, or replace a draft
the human hasn't touched yet, so the human's edits are never overwritten.

Usage:
  python3 review_queue.py add [JSON] [--date D]     # lints, then queues one draft; refuses hard fails
  python3 review_queue.py task [JSON] [--date D]    # a to-do for the human: an intro ask, a LinkedIn check-in
  python3 review_queue.py replace ID [JSON]         # swap in a rewritten draft, only if still untouched
  python3 review_queue.py parse [--date D] [--include-pending]
                                                    # decisions waiting to be acted on, across open queues
  python3 review_queue.py mark ID STATUS            # the kit finished it: status becomes "done, STATUS"
  python3 review_queue.py set ID STATUS             # copy a decision made elsewhere (in conversation) into the file
  python3 review_queue.py close ID REASON           # finished without sending (blocked, stale): frees the thread
  python3 review_queue.py note TEXT [--date D]      # a warning line at the top of the review file
  python3 review_queue.py summary [--date D]

Draft JSON for add:
  {"lead": {"id", "name", "email", "company", "title", "linkedin"},
   "channel": "email"|"linkedin"|"linkedin_connect", "touch": 1, "kind": "new"|"followup"|"reply",
   "tier", "segment", "angle", "subject", "body", "brief": {...}, "sources": [urls], "judge": {...},
   "thread_id", "reply_to" (their message id), "their_reply", "booking_only", "priority",
   "referral": true (allows a second person at a company already in the queue)}

Task JSON: {"lead": {...}, "task_type": "intro"|"linkedin_checkin"|"other", "task": "what to do",
            "via": "who to ask (intro)", "channel": "linkedin" (check-in), "body": "optional draft to send"}

In the .md file the human sets each status to:
  approve: ✅ approve yes send ok (and done, for tasks)      kill: ❌ kill no skip
  sent:    a LinkedIn message they sent by hand
  An item marked `auto` sends at the next sweep unless changed to ❌.
"""

import argparse
import datetime
import random
import re
import sys

import log as outreach_log
from log import FREE_MAIL
from _common import (QUEUE_DIR, append_jsonl, die, emit, load_config, locked, normalize, now, read_json_input,
                     read_jsonl, today, write_jsonl, write_text)
from lint import lint_draft

APPROVE = {"approve", "approved", "yes", "y", "send", "ok", "okay", "go", "done"}
KILL = {"kill", "killed", "no", "n", "skip", "reject", "drop"}
PRIORITY_MARK = "<!-- priority items go here -->"
NOTES_MARK = "<!-- notes go here -->"
MSG_OPEN, MSG_CLOSE = "<!-- message -->", "<!-- /message -->"
ITEM_RE = re.compile(r"^## \[([0-9]{8}-[0-9]{3})\]", re.M)
CHANNELS = ("email", "linkedin", "linkedin_connect")


def paths(date):
    return QUEUE_DIR / f"{date}.jsonl", QUEUE_DIR / f"{date}.md"


def date_of(qid):
    return f"{qid[:4]}-{qid[4:6]}-{qid[6:8]}"


def header(date):
    return (f"# Review queue, {date}\n\n"
            "Set each `status:` to ✅ (send) or ❌ (kill). Edit the subject or message between the message "
            "markers before approving, and the kit learns from your edits. LinkedIn messages are never sent "
            "for you: send them by hand, then set the status to `sent`. Items marked `auto` send at the next "
            "sweep unless you change them to ❌. Save before the next sweep runs.\n\n"
            f"{NOTES_MARK}\n\n{PRIORITY_MARK}\n")


def contact(item):
    lead = item.get("lead", {})
    return (lead.get("email") or lead.get("linkedin") or "").lower()


def render_item(item):
    lead = item.get("lead", {})
    who = " · ".join(x for x in (lead.get("name"), lead.get("title"), lead.get("company")) if x)
    flag = "PRIORITY · " if item.get("priority") else ""
    if item.get("kind") == "task":
        out = [f"## [{item['id']}] TASK · {flag}{who}", "status: pending", f"task: {item['task']}",
               "how: set ✅ when done (for a check-in, ✅ means they replied), ❌ to skip or if they didn't"]
        if lead.get("linkedin"):
            out.append(f"profile: {lead['linkedin']}")
        if item.get("body"):
            out += [MSG_OPEN, item["body"].strip(), MSG_CLOSE]
        return "\n".join(out + ["", "---", ""]) + "\n"

    route = [lead.get("email") or lead.get("linkedin") or "", item["channel"], f"touch {item['touch']}", item["kind"]]
    if item.get("tier"):
        route.append(f"tier {item['tier']}")
    if item.get("angle"):
        route.append(f"angle: {item['angle']}")
    meta = [f"status: {'auto' if item.get('auto') else 'pending'}", "to: " + " · ".join(r for r in route if r)]
    if item.get("auto"):
        meta.append("auto: sends at the next sweep unless you change the status to ❌")
    if item.get("spot_check"):
        meta.append("spot check: held for you from an auto-approved segment")
    if item["channel"] != "email":
        meta.append("send: by hand on LinkedIn" + (f" ({lead['linkedin']})" if lead.get("linkedin") else "")
                    + ", then set status to sent")
    brief = item.get("brief") or {}
    why = brief.get("reason_for_reviewer") or (brief.get("detail") or {}).get("fact")
    if why:
        meta.append(f"why: {why}")
    if item.get("sources"):
        meta.append("sources: " + ", ".join(item["sources"][:4]))
    if item.get("their_reply"):
        meta.append("their reply: " + normalize(item["their_reply"])[:300])
    checks = [f"lint {'pass' if item['lint']['pass'] else 'FAIL'}"] + item["lint"]["warn"]
    j = item.get("judge")
    if j:
        scores = j.get("scores") or {}
        low = [k for k, v in scores.items() if isinstance(v, (int, float)) and v < 4]
        checks.append(f"judge {j.get('verdict')}" + (f", low: {', '.join(low)}" if low else "")
                      + (f": {j['weakest_line']}" if j.get("verdict") != "pass" and j.get("weakest_line") else ""))
    meta.append("check: " + "; ".join(checks))
    msg = [f"Subject: {item.get('subject', '')}", ""] if item["channel"] == "email" and item["kind"] == "new" else []
    out = [f"## [{item['id']}] {flag}{who}", *meta, MSG_OPEN, *msg, item["body"].strip(), MSG_CLOSE, "", "---", ""]
    return "\n".join(out) + "\n"


def next_id(date, items):
    prefix = date.replace("-", "")
    seqs = [int(i["id"].split("-")[1]) for i in items if i.get("id", "").startswith(prefix)]
    return f"{prefix}-{max(seqs, default=0) + 1:03d}"


def insert_block(mpath, date, block, priority):
    text = mpath.read_text() if mpath.exists() else header(date)
    if priority and PRIORITY_MARK in text:
        text = text.replace(PRIORITY_MARK, PRIORITY_MARK + "\n" + block, 1)
    else:
        text = text.rstrip("\n") + "\n\n" + block
    write_text(mpath, text)


def auto_decision(item, config):
    """Decided once, at queue time, per engine/autonomy.md. Returns (auto, spot_check)."""
    rules = config.get("autonomy", {})
    level = rules.get("segments", {}).get(item.get("segment"), rules.get("default_level", 2))
    if level < 3 or item["channel"] != "email":
        return False, False
    if item["kind"] == "reply":
        return (level >= 4 and bool(item.get("booking_only"))), False
    j = item.get("judge") or {}
    scores = [v for v in (j.get("scores") or {}).values() if isinstance(v, (int, float))]
    if config.get("pipeline_mode") == "lean" or j.get("verdict") != "pass" or not scores or min(scores) < 4:
        return False, False
    if item["kind"] == "new" and (item.get("brief") or {}).get("senior"):
        return False, False
    if random.random() < rules.get("spot_check_rate", 0.1):
        return False, True
    return True, False


def add(draft, date):
    for k in ("lead", "channel", "touch", "body"):
        if not draft.get(k):
            die(f"draft is missing {k}")
    if draft["channel"] not in CHANNELS:
        die(f"channel must be one of {CHANNELS}")
    draft.setdefault("kind", "new" if int(draft["touch"]) == 1 else "followup")
    config = load_config()
    if config.get("pipeline_mode", "full") == "full" and draft["kind"] in ("new", "followup") \
            and draft["channel"] == "email" and not (draft.get("judge") or {}).get("verdict"):
        die("full pipeline mode: this draft has no judge result. Run the selector, writer, cutter and judge "
            "as separate subagent calls (engine/pipeline.md), then queue it with the judge's JSON")
    result = lint_draft(draft, config)
    if not result["pass"]:
        emit({"queued": False, "lint": result})
        sys.exit(1)

    jpath, mpath = paths(date)
    with locked():
        key = (contact(draft), draft["channel"], int(draft["touch"]), draft["kind"], draft.get("reply_to"))
        domain = key[0].split("@")[-1] if "@" in key[0] else None
        for it in outreach_log.open_queue_items(config):
            if (contact(it), it.get("channel"), int(it.get("touch") or 0), it.get("kind"), it.get("reply_to")) == key:
                die(f"{key[0]} {draft['channel']} touch {draft['touch']} ({draft['kind']}) is already queued as {it['id']}")
            if draft["kind"] == "new" and it.get("kind") == "new" and domain and domain not in FREE_MAIL \
                    and contact(it) != key[0] and contact(it).endswith("@" + domain) and not draft.get("referral"):
                die(f"someone else at {domain} is already queued ({it['id']}); one person per company at a time")
        auto, spot = auto_decision(draft, config)
        item = dict(draft, id=next_id(date, read_jsonl(jpath)), lint=result, queued_at=now(), auto=auto,
                    spot_check=spot, original_subject=draft.get("subject", ""), original_body=draft["body"])
        append_jsonl(jpath, item)
        insert_block(mpath, date, render_item(item), item.get("priority"))
    emit({"queued": True, "id": item["id"], "auto": auto, "spot_check": spot, "file": str(mpath), "lint": result})


def task(t, date):
    if not t.get("lead") or not t.get("task"):
        die("a task needs lead and task")
    jpath, mpath = paths(date)
    with locked():
        item = dict(t, kind="task", touch=0, channel=t.get("channel", "email"),
                    id=next_id(date, read_jsonl(jpath)), queued_at=now())
        append_jsonl(jpath, item)
        insert_block(mpath, date, render_item(item), t.get("priority"))
    emit({"queued": True, "id": item["id"], "file": str(mpath)})


def blocks(text):
    starts = [(m.start(), m.group(1)) for m in ITEM_RE.finditer(text)]
    for i, (pos, qid) in enumerate(starts):
        yield qid, pos, (starts[i + 1][0] if i + 1 < len(starts) else len(text))


def read_block(chunk):
    status = "pending"
    for line in chunk.splitlines()[1:]:
        if line.strip() == MSG_OPEN:
            break
        m = re.match(r"^status:\s*(.*)$", line.strip(), re.I)
        if m:
            status = m.group(1).strip()
            break
    subject, body = None, ""
    if MSG_OPEN in chunk:
        after = chunk.split(MSG_OPEN, 1)[1]
        # If the closing marker got deleted while editing, the message runs to the item's --- line.
        inner = (after.split(MSG_CLOSE, 1)[0] if MSG_CLOSE in after else re.split(r"^---\s*$", after, flags=re.M)[0])
        inner = inner.strip("\n").split("\n")
        if inner and inner[0].lower().startswith("subject:"):
            subject = inner.pop(0).split(":", 1)[1].strip()
        body = "\n".join(inner).strip()
    return {"status": status, "subject": subject, "body": body}


def read_md(mpath):
    """{id: {"status", "subject", "body"}} as the human left them."""
    if not mpath.exists():
        return {}
    text = mpath.read_text()
    return {qid: read_block(text[a:b]) for qid, a, b in blocks(text)}


def decision(status):
    s = status.replace("️", "").strip()
    first = re.split(r"[\s,.:;!()]+", s.lower())[0] if s else ""
    if not s or first == "pending":
        return "pending"
    if s.lower().startswith("done,") or first == "expired":
        return "done"  # written by the kit after acting on it
    if first == "auto":
        return "auto"
    if s[0] in "✅✔☑" or first in APPROVE:
        return "approve"
    if s[0] in "❌✖✗❎" or first in KILL:
        return "kill"
    if first == "sent":
        return "sent-by-hand"
    return "unrecognized"


def queue_dates(config):
    start = datetime.date.today() - datetime.timedelta(days=config.get("queue", {}).get("max_age_days", 14))
    out = []
    for f in sorted(QUEUE_DIR.glob("*.jsonl")) if QUEUE_DIR.exists() else []:
        try:
            if datetime.date.fromisoformat(f.stem) >= start:
                out.append(f.stem)
        except ValueError:
            pass
    return out


def parse(date, include_pending=False, events=None, config=None):
    jpath, mpath = paths(date)
    md = read_md(mpath)
    events = outreach_log.read_jsonl(outreach_log.LOG) if events is None else events
    window = (config or load_config()).get("volume", {}).get("skip_if_contacted_within_days", 90)
    out = []
    for item in read_jsonl(jpath):
        human = md.get(item["id"])
        if human is None or item.get("closed"):
            continue
        d = decision(human["status"])
        if d == "done" or (d in ("pending", "unrecognized") and not include_pending) \
                or outreach_log.has(item["id"], events)["done"]:
            continue
        if item.get("kind") == "task":
            out.append({**item, "decision": d})
            continue
        subject = human["subject"] if human["subject"] is not None else item.get("subject", "")
        body = human["body"] or item["body"]
        edited = normalize(body) != normalize(item["original_body"]) or \
            normalize(subject) != normalize(item.get("original_subject", ""))
        lint = lint_draft(dict(item, subject=subject, body=body)) if edited else item["lint"]
        if d == "auto" and edited:
            d = "approve"  # the human touched it, so it's their call now
        out.append({**{k: v for k, v in item.items() if k != "lint"}, "decision": d, "subject": subject,
                    "body": body, "edited": edited, "lint": lint,
                    "blocked": outreach_log.blocked_reason(item, events, window) if d in ("approve", "auto") else None})
    return out


def find(qid):
    jpath, mpath = paths(date_of(qid))
    if not mpath.exists():
        die(f"no queue file for {qid}")
    return jpath, mpath


def mark(qid, status, raw=False):
    _, mpath = find(qid)
    line = f"status: {status}" if raw else f"status: done, {status} ({now()})"
    with locked():
        text = mpath.read_text()
        for bid, a, b in blocks(text):
            if bid == qid:
                chunk = text[a:b]
                new = re.sub(r"^status:.*$", lambda _: line, chunk, count=1, flags=re.M | re.I)
                if new == chunk:
                    die(f"{qid} has no status line")
                write_text(mpath, text[:a] + new + text[b:])
                break
        else:
            die(f"{qid} not found in {mpath.name}")
    emit({"id": qid, "status": status})


def close(qid, reason):
    jpath, _ = find(qid)
    with locked():
        mark(qid, reason)
        write_jsonl(jpath, [dict(i, closed=reason) if i["id"] == qid else i for i in read_jsonl(jpath)])


def replace(qid, draft):
    jpath, mpath = find(qid)
    config = load_config()
    with locked():
        items = read_jsonl(jpath)
        item = next((i for i in items if i["id"] == qid), None)
        human = read_md(mpath).get(qid)
        if not item or not human:
            die(f"{qid} not found")
        if decision(human["status"]) not in ("pending", "auto") or normalize(human["body"]) != normalize(item["body"]):
            die(f"{qid} was already reviewed or edited by the human; leaving it alone")
        new = dict(item, **{k: v for k, v in draft.items() if k in ("subject", "body", "brief", "judge", "angle", "sources")})
        result = lint_draft(new, config)
        if not result["pass"]:
            emit({"replaced": False, "lint": result})
            sys.exit(1)
        new.update(lint=result, original_subject=new.get("subject", ""), original_body=new["body"])
        new["auto"], new["spot_check"] = auto_decision(new, config)
        write_jsonl(jpath, [new if i["id"] == qid else i for i in items])
        text = mpath.read_text()
        for bid, a, b in blocks(text):
            if bid == qid:
                write_text(mpath, text[:a] + render_item(new) + "\n" + text[b:].lstrip("\n"))
                break
    emit({"replaced": True, "id": qid, "lint": result})


def note(text, date):
    _, mpath = paths(date)
    with locked():
        body = mpath.read_text() if mpath.exists() else header(date)
        line = f"> ⚠ {text} ({now()[11:16]})"
        body = body.replace(NOTES_MARK, NOTES_MARK + "\n" + line, 1) if NOTES_MARK in body else line + "\n\n" + body
        write_text(mpath, body)
    emit({"noted": text, "file": str(mpath)})


def summary(date, config):
    jpath, mpath = paths(date)
    md = read_md(mpath)
    counts, unrecognized, first_touches = {}, [], 0
    for item in read_jsonl(jpath):
        status = md.get(item["id"], {}).get("status", "pending")
        d = decision(status)
        key = f"{item.get('kind')}:{d}"
        counts[key] = counts.get(key, 0) + 1
        if d == "unrecognized":
            unrecognized.append({"id": item["id"], "status": status})
        if item.get("kind") == "new" and item.get("channel") == "email":
            first_touches += 1
    events = outreach_log.read_jsonl(outreach_log.LOG)
    waiting = 0
    for d in queue_dates(config):
        if d == date:
            continue
        older_md = read_md(paths(d)[1])
        for x in parse(d, True, events, config):
            if x["decision"] == "unrecognized":
                unrecognized.append({"id": x["id"], "status": older_md.get(x["id"], {}).get("status")})
            if x["decision"] in ("pending", "unrecognized"):
                waiting += 1
    emit({"date": date, "file": str(mpath), "email_first_touches_queued": first_touches, "counts": counts,
          "unrecognized_statuses": unrecognized, "undecided_in_earlier_queues": waiting})


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("add", "task"):
        p = sub.add_parser(name)
        p.add_argument("json", nargs="?")
        p.add_argument("--date")
    p = sub.add_parser("replace")
    p.add_argument("id")
    p.add_argument("json", nargs="?")
    p = sub.add_parser("parse")
    p.add_argument("--date", help="one day only; default is every open queue")
    p.add_argument("--include-pending", action="store_true", help="also list undecided items")
    for name in ("mark", "set", "close"):
        p = sub.add_parser(name)
        p.add_argument("id")
        p.add_argument("status")
    p = sub.add_parser("note")
    p.add_argument("text")
    p.add_argument("--date")
    p = sub.add_parser("summary")
    p.add_argument("--date")
    args = ap.parse_args()
    date = getattr(args, "date", None) or today()

    if args.cmd in ("add", "task", "replace"):
        data = read_json_input(args.json)
        if not isinstance(data, dict):
            die("input must be a JSON object")
        if args.cmd == "add":
            add(data, date)
        elif args.cmd == "task":
            task(data, date)
        else:
            replace(args.id, data)
    elif args.cmd == "parse":
        config = load_config()
        dates = [args.date] if args.date else queue_dates(config)
        events = outreach_log.read_jsonl(outreach_log.LOG)
        emit([x for d in dates for x in parse(d, args.include_pending, events, config)])
    elif args.cmd == "mark":
        mark(args.id, args.status)
    elif args.cmd == "set":
        if decision(args.status) in ("done", "unrecognized"):
            die("set takes a reviewer decision: ✅, ❌, sent, or a word like approve or kill")
        mark(args.id, args.status, raw=True)
    elif args.cmd == "close":
        close(args.id, args.status)
    elif args.cmd == "note":
        note(args.text, date)
    elif args.cmd == "summary":
        summary(date, load_config())


if __name__ == "__main__":
    main()
