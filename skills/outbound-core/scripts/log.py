#!/usr/bin/env python3
"""The append-only outreach log (state/outreach-log.jsonl) and the run log (state/runs.jsonl).
Nothing in either is ever edited or deleted.

Usage:
  python3 log.py add '{"event": "sent", ...}'    # or pipe JSON on stdin
  python3 log.py claim QUEUE_ID                  # call right before sending: refuses repeats and the daily cap
  python3 log.py release QUEUE_ID                # the send failed and nothing went out
  python3 log.py unconfirmed [--older-than 15]   # claimed over N minutes ago, never confirmed: check Sent/Drafts
  python3 log.py undelivered                     # draft-mode emails not yet seen in the Sent folder
  python3 log.py seen EMAIL_OR_DOMAIN            # contacted? stopped? never-contact? waiting in a queue?
  python3 log.py has QUEUE_ID_OR_MESSAGE_ID      # already sent, killed, or logged?
  python3 log.py due [--date YYYY-MM-DD]         # threads due for their next touch
  python3 log.py next-due QUEUE_ID               # when this send's next touch gets drafted (for the CRM task)
  python3 log.py budget                          # today's sends, the cap, and how many new leads fit
  python3 log.py report [--days 7] [--json]
  python3 log.py run SKILL ok|failed|partial ["note"]
  python3 log.py runs [--days 7] [--skill SKILL]

Events and their required fields:
  sent     id, email, channel, touch, kind (new|followup|reply), body, draft
           (also name, company, lead_id, tier, segment, angle, rung, subject, thread_id, message_id,
            mode (send|draft|manual|auto), spot_check)
  killed   id, email, touch (also channel, kind, segment, angle, tier, spot_check)
  reply    email, category (positive|engaged|question|referral|not-now|not-interested|unsubscribe|ooo|other),
           also channel, message_id, back_on (for ooo)
  checkin  email, channel, replied (false; a LinkedIn reply is logged as a reply event)
  stop     email, reason
  bounce   email
  meeting  email
  delivered id (a draft-mode email the human actually sent; at = when Gmail sent it)
  intro    via (also email, name)
  skipped  lead_id, reason (email if known)
"""

import argparse
import datetime
import sys

import edit_rate
from _common import (CORE, LOG, QUEUE_DIR, RUNS, append_jsonl, die, emit, load_config, locked, md_bullets, now,
                     parse_date, parse_dt, read_json_input, read_jsonl)

REQUIRED = {
    "sent": ["id", "email", "channel", "touch", "kind", "body", "draft"],
    "sending": ["id"],
    "released": ["id"],
    "killed": ["id", "email", "touch"],
    "reply": ["email", "category"],
    "checkin": ["email", "channel"],
    "stop": ["email", "reason"],
    "bounce": ["email"],
    "meeting": ["email"],
    "delivered": ["id"],
    "intro": ["via"],
    "skipped": ["lead_id", "reason"],
}
REPLY_CATEGORIES = {"positive", "engaged", "question", "referral", "not-now", "not-interested", "unsubscribe", "ooo", "other"}
FREE_MAIL = {"gmail.com", "googlemail.com", "yahoo.com", "hotmail.com", "outlook.com", "live.com", "icloud.com",
             "me.com", "aol.com", "proton.me", "protonmail.com", "msn.com", "gmx.com"}


def at(e):
    return parse_dt(e.get("at"))


def add(entry):
    event = entry.get("event")
    if event not in REQUIRED:
        die(f"unknown event {event!r}, expected one of {sorted(REQUIRED)}")
    missing = [k for k in REQUIRED[event] if entry.get(k) in (None, "")]
    if missing:
        die(f"{event} event is missing {missing}")
    if event == "reply" and entry["category"] not in REPLY_CATEGORIES:
        die(f"reply category must be one of {sorted(REPLY_CATEGORIES)}")
    if entry.get("email"):
        entry["email"] = entry["email"].strip().lower()
    with locked():
        dup = duplicate_of(entry, read_jsonl(LOG))
        if dup:
            return {"duplicate": True, "existing": dup}
        entry.setdefault("at", now())
        append_jsonl(LOG, entry)
    return entry


def duplicate_of(entry, events):
    if entry["event"] in ("sent", "killed") and entry.get("id"):
        for e in events:
            if e.get("id") == entry["id"] and e.get("event") in ("sent", "killed"):
                return e
    if entry["event"] == "delivered":
        for e in events:
            if e.get("event") == "delivered" and e.get("id") == entry.get("id"):
                return e
    mid = entry.get("message_id")
    if entry["event"] in ("reply", "bounce", "meeting") and mid:
        for e in events:
            if e.get("message_id") == mid and e.get("event") == entry["event"]:
                return e
    return None


def open_claims(events, queue_id=None):
    """Claims with no matching sent, killed or release yet, oldest first."""
    pending = {}
    for e in sorted(events, key=at):
        qid = e.get("id")
        if queue_id and qid != queue_id:
            continue
        if e.get("event") == "sending":
            pending.setdefault(qid, []).append(e)
        elif e.get("event") in ("released", "sent", "killed") and pending.get(qid):
            pending[qid] = [] if e["event"] != "released" else pending[qid][1:]
    return [c for claims in pending.values() for c in claims]


def sends_today(events):
    """Emails sent or put in drafts today (drafts count: they go out from the same inbox), plus open claims."""
    today = datetime.date.today()
    sent = sum(1 for e in events if e.get("event") == "sent" and e.get("channel") == "email" and e.get("kind")
               and e.get("mode") != "manual" and at(e).date() == today)
    return sent + sum(1 for c in open_claims(events) if at(c).date() == today)


def claim(queue_id, config):
    with locked():
        events = read_jsonl(LOG)
        mine = [e for e in events if e.get("id") == queue_id]
        for e in mine:
            if e.get("event") in ("sent", "killed"):
                return {"ok": False, "why": f"already {e['event']}"}
        if open_claims(events, queue_id):
            return {"ok": False, "why": "already claimed by another run; check the Sent folder before retrying"}
        cap = config.get("volume", {}).get("max_sends_per_day")
        count = sends_today(events)
        if cap and count >= cap:
            return {"ok": False, "why": f"daily send cap reached ({count}/{cap}); it goes out tomorrow"}
        append_jsonl(LOG, {"event": "sending", "id": queue_id, "at": now()})
    return {"ok": True, "sends_today": count + 1, "cap": cap}


def unconfirmed(events, older_than_minutes=15):
    """Claims old enough that the run making them has surely finished or crashed."""
    cutoff = datetime.datetime.now().astimezone() - datetime.timedelta(minutes=older_than_minutes)
    return [{"id": c["id"], "claimed_at": c["at"]} for c in open_claims(events) if at(c) <= cutoff]


def delivered_at(events):
    """When each draft-mode email actually went out, from delivered events."""
    return {e["id"]: e["at"] for e in events if e.get("event") == "delivered" and e.get("id")}


def undelivered(events):
    done = delivered_at(events)
    return [{"id": e["id"], "email": e.get("email"), "subject": e.get("subject"), "thread_id": e.get("thread_id"),
             "touch": e.get("touch"), "drafted_at": e.get("at")}
            for e in events if e.get("event") == "sent" and e.get("mode") == "draft" and e.get("id") not in done]


def by_email(events):
    out = {}
    for e in events:
        if e.get("email"):
            out.setdefault(e["email"].lower(), []).append(e)
    for evs in out.values():
        evs.sort(key=at)
    return out


def never_contact_list():
    out = set()
    for item in md_bullets(CORE / "company" / "crm.md", "Never contact"):
        token = item.split()[0].strip().lower().lstrip("@").rstrip(",;")
        if token:
            out.add(token)
    return out


def open_queue_items(config, events=None):
    """Queue items from the last queue.max_age_days that haven't been sent or killed."""
    events = read_jsonl(LOG) if events is None else events
    done = {e["id"] for e in events if e.get("event") in ("sent", "killed") and e.get("id")}
    cutoff = datetime.date.today() - datetime.timedelta(days=config.get("queue", {}).get("max_age_days", 14))
    out = []
    for f in sorted(QUEUE_DIR.glob("*.jsonl")) if QUEUE_DIR.exists() else []:
        try:
            if datetime.date.fromisoformat(f.stem) < cutoff:
                continue
        except ValueError:
            continue
        out += [i for i in read_jsonl(f) if i["id"] not in done and not i.get("closed")]
    return out


def stop_reason(evs, after=None):
    """Why this person's sequences have ended, looking at events after `after` (or all)."""
    for e in evs:
        if after and at(e) < after:
            continue
        ev, cat = e.get("event"), e.get("category")
        if ev in ("bounce", "meeting"):
            return ev
        if ev == "stop":
            return f"stopped: {e.get('reason')}"
        if ev == "reply" and cat != "ooo":
            return "unsubscribed" if cat == "unsubscribe" else f"replied ({cat})"
    return None


FOREVER = ("bounce", "unsubscribed", "replied (not-interested)")


def family(channel):
    """A LinkedIn connection note and the messages after it are one thread."""
    return "linkedin" if str(channel or "").startswith("linkedin") else (channel or "email")


def current_sequence(evs, channel):
    """Events since the latest touch 1 on this channel family: an old, finished sequence doesn't count."""
    sends = [e for e in evs if e["event"] == "sent" and e.get("kind") != "reply" and family(e.get("channel")) == channel]
    starts = [e for e in sends if int(e.get("touch", 1)) == 1]
    if not starts:
        return [], evs
    start = at(starts[-1])
    return [e for e in sends if at(e) >= start], [e for e in evs if at(e) >= start]


def seen(key, events, config):
    """Takes an email, or a bare domain when the email isn't known yet (before a paid lookup)."""
    key = key.strip().lower()
    is_email = "@" in key
    domain = key.split("@")[-1]
    window = config.get("volume", {}).get("skip_if_contacted_within_days", 90)
    since = datetime.datetime.now().astimezone() - datetime.timedelta(days=window)
    never = never_contact_list()
    mine = by_email(events).get(key, []) if is_email else []
    recent = any(e["event"] == "sent" and at(e) >= since for e in mine)
    stopped = stop_reason(mine)
    queued = [i["id"] for i in open_queue_items(config, events)
              if (i.get("lead", {}).get("email") or "").lower() == key
              or (not is_email and (i.get("lead", {}).get("email") or "").lower().endswith("@" + domain))]
    colleagues = []
    if domain not in FREE_MAIL:
        colleagues = sorted({e["email"] for e in events if e.get("event") == "sent" and e.get("email") != key
                             and e["email"].endswith("@" + domain) and at(e) >= since})
    blocked = key in never or domain in never
    return {
        "key": key,
        "contacted": any(e["event"] == "sent" for e in mine),
        "contacted_recently": recent,
        "stopped": stopped,
        "never_contact": blocked,
        "pending_in_queue": queued,
        "colleagues_contacted_recently": colleagues,
        "hold": bool(recent or blocked or queued or colleagues
                     or any(stop_reason([e]) in FOREVER for e in mine)),
    }


def has(key, events):
    """A queue id that was sent or killed, or an email message_id already logged."""
    for e in events:
        if (e.get("id") == key and e.get("event") in ("sent", "killed")) or \
                (e.get("message_id") == key and e.get("event") in ("reply", "bounce", "meeting")):
            return {"done": True, "event": e["event"], "at": e.get("at")}
    return {"done": False}


def blocked_reason(item, events, window_days=90):
    """Why an approved item must not send now, or None. review_queue.py parse attaches this to each item."""
    email = (item.get("lead", {}).get("email") or "").lower()
    if not email or item.get("kind") == "task":
        return None
    never = never_contact_list()
    if email in never or email.split("@")[-1] in never:
        return "on the never-contact list"
    evs = by_email(events).get(email, [])
    forever = next((r for r in (stop_reason([e]) for e in evs) if r in FOREVER), None)
    if forever:
        return f"they {forever}" if forever != "bounce" else "their address bounced"
    if item.get("kind") == "reply":
        return None
    since = stop_reason(evs, after=parse_dt(item.get("queued_at")))
    if since:
        return f"sequence ended after this was drafted: {since}"
    since_window = datetime.datetime.now().astimezone() - datetime.timedelta(days=window_days)
    for e in evs:
        if e["event"] == "sent" and e.get("id") != item["id"] and e.get("kind") == item.get("kind") \
                and family(e.get("channel")) == family(item.get("channel")) and at(e) >= since_window \
                and int(e.get("touch", 0)) == int(item.get("touch", 0)):
            return f"touch {item['touch']} was already sent to them ({e.get('id')})"
    return None


def due_date(first_sent, last_sent, next_touch, spacing):
    if next_touch - 1 < len(spacing):
        return parse_date(first_sent) + datetime.timedelta(days=spacing[next_touch - 1])
    return parse_date(last_sent) + datetime.timedelta(days=4)


def due(events, config, on=None):
    on = on or datetime.date.today()
    seq = config.get("sequence", {})
    max_touches = seq.get("max_touches", 3)
    spacing = seq.get("spacing_days", [0, 4, 8])
    if not isinstance(spacing, list) or not spacing:
        die("sequence.spacing_days in config.json must be a list of days, like [0, 4, 8]")
    queue = open_queue_items(config, events)
    in_queue = {((i.get("lead", {}).get("email") or "").lower(), family(i.get("channel")), int(i.get("touch") or 0))
                for i in queue if i.get("kind") in ("new", "followup")}
    checkin_open = {(i.get("lead", {}).get("email") or "").lower() for i in queue
                    if i.get("kind") == "task" and i.get("task_type") == "linkedin_checkin"}

    went_out = delivered_at(events)
    out = []
    for email, all_evs in by_email(events).items():
        if any(stop_reason([e]) in FOREVER for e in all_evs):
            continue
        families = sorted({family(e.get("channel")) for e in all_evs if e["event"] == "sent" and e.get("kind") != "reply"})
        for channel in families:
            touches, evs = current_sequence(all_evs, channel)
            if not touches or stop_reason(evs):
                continue
            # A draft-mode touch only counts once the human has actually sent it, and from when they did.
            if any(t.get("mode") == "draft" and t["id"] not in went_out for t in touches):
                continue
            touches = [dict(t, at=went_out.get(t["id"], t["at"])) for t in touches]
            if any(e["event"] == "killed" and int(e.get("touch", 1)) > 1 and family(e.get("channel", channel)) == channel
                   for e in evs):
                continue  # the human killed a follow-up, so this sequence ends
            last = touches[-1]
            next_touch = int(last["touch"]) + 1
            if next_touch > max_touches or (email, channel, next_touch) in in_queue:
                continue
            due_on = due_date(touches[0]["at"], last["at"], next_touch, spacing)
            for r in evs:
                if r["event"] == "reply" and r.get("category") == "ooo" and r.get("back_on") and at(r) > at(last):
                    due_on = max(due_on, parse_date(r["back_on"]) + datetime.timedelta(days=1))
            if on < due_on:
                continue
            needs_checkin = channel == "linkedin" and not any(
                e["event"] == "checkin" and family(e.get("channel")) == "linkedin" and at(e) > at(last) for e in evs)
            if needs_checkin and email in checkin_open:
                continue
            out.append({
                "email": email, "name": last.get("name"), "company": last.get("company"), "lead_id": last.get("lead_id"),
                "channel": channel, "last_channel": last.get("channel"), "next_touch": next_touch, "last_sent": last["at"],
                "days_since": (on - parse_date(last["at"])).days, "overdue": (on - due_on).days > 1,
                "needs_checkin": needs_checkin, "thread_id": last.get("thread_id"), "subject": last.get("subject"),
                "tier": last.get("tier"), "segment": last.get("segment"), "angle": last.get("angle"),
                "rung": last.get("rung"), "previous_touches": [t["body"] for t in touches],
            })
    return sorted(out, key=lambda x: (not x["overdue"], x["last_sent"]))


def next_due(queue_id, events, config):
    """The weekday the next touch after this send gets drafted, counted from when it really went out."""
    sent = next((e for e in events if e.get("event") == "sent" and e.get("id") == queue_id), None)
    if not sent:
        return {"id": queue_id, "error": "no sent event with this id"}
    went_out = delivered_at(events)
    if sent.get("mode") == "draft" and queue_id not in went_out:
        return {"id": queue_id, "next_touch": None, "why": "still in Drafts; date the task once it's delivered"}
    seq = config.get("sequence", {})
    spacing = seq.get("spacing_days", [0, 4, 8])
    next_touch = int(sent.get("touch", 1)) + 1
    if sent.get("kind") == "reply" or next_touch > seq.get("max_touches", 3):
        return {"id": queue_id, "next_touch": None, "why": "no further touch in this sequence"}
    ended = stop_reason(by_email(events).get(sent["email"], []), after=at(sent))
    if ended:
        return {"id": queue_id, "next_touch": None, "why": f"sequence ended: {ended}"}
    touches, _ = current_sequence(by_email(events).get(sent["email"], []), family(sent.get("channel")))
    touches = [dict(t, at=went_out.get(t["id"], t["at"])) for t in touches if at(t) <= at(sent)] or [sent]
    on = due_date(touches[0]["at"], went_out.get(queue_id, sent["at"]), next_touch, spacing)
    while on.weekday() >= 5:  # follow-ups run on weekdays
        on += datetime.timedelta(days=1)
    return {"id": queue_id, "email": sent["email"], "next_touch": next_touch, "due": on.isoformat()}


def budget(events, config):
    vol = config.get("volume", {})
    cap = vol.get("max_sends_per_day")
    used = sends_today(events)
    followups = sum(1 for d in due(events, config) if not d["needs_checkin"] and d["channel"] == "email")
    room = (cap - used - followups) if cap else 10 ** 6
    return {"sends_today": used, "cap": cap, "followups_due": followups,
            "new_leads_today": max(0, min(vol.get("new_leads_per_day", 20), room))}


def report(events, days):
    start = datetime.date.today() - datetime.timedelta(days=days - 1)
    window = [e for e in events if parse_date(e.get("at")) >= start]
    sends = [e for e in window if e["event"] == "sent" and e.get("kind") != "reply"]
    touches_by_email = {}
    for e in events:
        if e.get("event") == "sent" and e.get("kind") != "reply":
            touches_by_email.setdefault(e["email"], []).append(e)

    def source(e):
        prior = [t for t in touches_by_email.get(e["email"], []) if at(t) <= at(e)]
        return prior[-1] if prior else {}

    replies = [e for e in window if e["event"] == "reply" and e.get("category") not in ("ooo", "unsubscribe")]
    totals = {
        "sent_first_touch": sum(1 for e in sends if int(e.get("touch", 1)) == 1),
        "sent_followups": sum(1 for e in sends if int(e.get("touch", 1)) > 1),
        "killed_in_review": sum(1 for e in window if e["event"] == "killed"),
        "replies": len(replies),
        "positive_replies": sum(1 for e in replies if e.get("category") == "positive"),
        "meetings": sum(1 for e in window if e["event"] == "meeting"),
        "bounces": sum(1 for e in window if e["event"] == "bounce"),
        "unsubscribes": sum(1 for e in window if e["event"] == "reply" and e.get("category") == "unsubscribe"),
        "skipped_or_held": sum(1 for e in window if e["event"] == "skipped"),
    }
    breakdowns = {}
    for dim in ("angle", "segment", "tier"):
        rows = {}

        def row(k):
            return rows.setdefault(k, {"sent": 0, "replies": 0, "positive": 0, "meetings": 0})

        for e in sends:
            row(str(e.get(dim) or "unknown"))["sent"] += 1
        for e in replies + [e for e in window if e["event"] == "meeting"]:
            r = row(str(source(e).get(dim) or "unknown"))
            if e["event"] == "meeting":
                r["meetings"] += 1
            else:
                r["replies"] += 1
                r["positive"] += e.get("category") == "positive"
        edits = edit_rate.stats(edit_rate.reviewed(window), dim)
        for k, r in rows.items():
            r["untouched_rate"] = edits.get(k, {}).get("untouched_rate")
        breakdowns[dim] = rows
    return {"from": start.isoformat(), "to": datetime.date.today().isoformat(), "totals": totals, "by": breakdowns}


def render(rep):
    lines = [f"# Outreach report, {rep['from']} to {rep['to']}", ""]
    if not any(rep["totals"].values()):
        lines += ["No activity in this period.", ""]
    lines += ["| Metric | Count |", "|---|---|"]
    lines += [f"| {k.replace('_', ' ')} | {v} |" for k, v in rep["totals"].items()]
    for dim, rows in rep["by"].items():
        if not rows:
            continue
        lines += ["", f"## By {dim}", "", f"| {dim} | sent | replies | positive | meetings | untouched |",
                  "|---|---|---|---|---|---|"]
        for k, r in sorted(rows.items()):
            rate = "" if r["untouched_rate"] is None else f"{round(r['untouched_rate'] * 100)}%"
            lines.append(f"| {k} | {r['sent']} | {r['replies']} | {r['positive']} | {r['meetings']} | {rate} |")
    return "\n".join(lines)


def run(skill, status, note):
    entry = {"skill": skill, "status": status, "note": note or "", "at": now()}
    with locked():
        append_jsonl(RUNS, entry)
    return entry


def runs(days, skill=None):
    start = datetime.date.today() - datetime.timedelta(days=days - 1)
    return [r for r in read_jsonl(RUNS) if parse_date(r.get("at")) >= start and (not skill or r.get("skill") == skill)]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("add").add_argument("json", nargs="?")
    sub.add_parser("claim").add_argument("queue_id")
    sub.add_parser("release").add_argument("queue_id")
    sub.add_parser("unconfirmed").add_argument("--older-than", type=int, default=15, help="minutes")
    sub.add_parser("undelivered")
    sub.add_parser("seen").add_argument("key")
    sub.add_parser("has").add_argument("key")
    sub.add_parser("due").add_argument("--date")
    sub.add_parser("budget")
    sub.add_parser("next-due").add_argument("queue_id")
    p = sub.add_parser("report")
    p.add_argument("--days", type=int, default=7)
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("run")
    p.add_argument("skill")
    p.add_argument("status", choices=["ok", "failed", "partial"])
    p.add_argument("note", nargs="?")
    p = sub.add_parser("runs")
    p.add_argument("--days", type=int, default=7)
    p.add_argument("--skill")
    args = ap.parse_args()

    events = read_jsonl(LOG)
    if args.cmd == "add":
        entry = read_json_input(args.json)
        if not isinstance(entry, dict):
            die("event must be a JSON object")
        emit(add(entry))
    elif args.cmd == "claim":
        result = claim(args.queue_id, load_config())
        emit(result)
        return 0 if result["ok"] else 1
    elif args.cmd == "release":
        emit(add({"event": "released", "id": args.queue_id}))
    elif args.cmd == "unconfirmed":
        emit(unconfirmed(events, args.older_than))
    elif args.cmd == "undelivered":
        emit(undelivered(events))
    elif args.cmd == "seen":
        emit(seen(args.key, events, load_config()))
    elif args.cmd == "has":
        emit(has(args.key, events))
    elif args.cmd == "due":
        emit(due(events, load_config(), parse_date(args.date) if args.date else None))
    elif args.cmd == "next-due":
        emit(next_due(args.queue_id, events, load_config()))
    elif args.cmd == "budget":
        emit(budget(events, load_config()))
    elif args.cmd == "report":
        rep = report(events, args.days)
        if args.json:
            emit(rep)
        else:
            print(render(rep))
    elif args.cmd == "run":
        emit(run(args.skill, args.status, args.note))
    elif args.cmd == "runs":
        emit(runs(args.days, args.skill))
    return 0


if __name__ == "__main__":
    sys.exit(main())
