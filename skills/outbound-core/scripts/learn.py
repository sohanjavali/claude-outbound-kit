#!/usr/bin/env python3
"""Learning from what the human sends. Every reviewed message goes into the example bank, examples
that got replies rank first, and edits repeated often enough become short rules.

Usage:
  python3 learn.py ingest                 # new sends → example bank, mark replies; prints new diffs
  python3 learn.py diffs [--days 7]       # every edited draft in the window, to spot repeated edits
  python3 learn.py rules                  # current learned rules and the cap
  python3 learn.py add-rule "RULE" --why "REASON" --evidence ID ID ID
                                          # needs learning.rule_evidence (3) edited sends showing the same change
  python3 learn.py retire "TEXT"          # remove the rule containing TEXT (to merge, or when it's stale)
"""

import argparse
import datetime
import difflib
import re
import sys

import voice
from _common import (CORE, EXAMPLES, LOG, STATE, emit, load_config, locked, normalize, parse_date,
                     parse_dt, read_jsonl, today, write_jsonl, write_text)

RULES = CORE / "person" / "learned-rules.md"
LEARNED_IDS = STATE / "learned-ids.txt"
RULE_RE = re.compile(r"^\s*-\s+(?!\[)(.+)$")
REPLIED = {"positive", "engaged", "question", "referral", "not-now", "other"}


def edited(e):
    return normalize(e.get("draft", "")) != normalize(e.get("body", ""))


def diff(e):
    lines = difflib.unified_diff(e.get("draft", "").splitlines(), e["body"].splitlines(), "draft", "sent",
                                 lineterm="", n=0)
    return {"id": e["id"], "segment": e.get("segment"), "angle": e.get("angle"), "diff": "\n".join(list(lines)[2:])}


def human_sends(events):
    """Sends a human decided on. Auto-sent drafts aren't evidence of what the human wants."""
    return [e for e in events if e.get("event") == "sent" and e.get("kind") != "reply" and e.get("mode") != "auto"]


def ingest():
    events = read_jsonl(LOG)
    with locked():
        done = set(LEARNED_IDS.read_text().split()) if LEARNED_IDS.exists() else set()
        new, diffs = 0, []
        for e in human_sends(events):
            if e["id"] in done:
                continue
            voice.add({"source": "kit-sent", "id": e["id"], "email": e.get("email"), "channel": e.get("channel"),
                       "touch": e.get("touch"), "angle": e.get("angle"), "segment": e.get("segment"),
                       "tier": e.get("tier"), "subject": e.get("subject", ""), "body": e["body"],
                       "edited": edited(e), "got_reply": False})
            LEARNED_IDS.parent.mkdir(parents=True, exist_ok=True)
            with LEARNED_IDS.open("a") as f:
                f.write(e["id"] + "\n")  # one at a time, so a crash never re-adds an example
            new += 1
            if edited(e):
                diffs.append(diff(e))

        # Examples whose message got a reply rank first in voice.py pick.
        replies = {}
        for e in events:
            if e.get("event") == "reply" and e.get("category") in REPLIED:
                replies.setdefault(e["email"], []).append(parse_dt(e["at"]))
        sent_at = {e["id"]: parse_dt(e["at"]) for e in events if e.get("event") == "sent"}
        bank, marked = read_jsonl(EXAMPLES), 0
        for x in bank:
            if x.get("source") == "kit-sent" and not x.get("got_reply") and x.get("id") in sent_at:
                if any(t > sent_at[x["id"]] for t in replies.get(x.get("email"), [])):
                    x["got_reply"] = True
                    marked += 1
        if marked:
            write_jsonl(EXAMPLES, bank)
    return {"ingested": new, "edited": len(diffs), "newly_marked_replied": marked, "diffs": diffs}


def diffs_since(days):
    start = datetime.date.today() - datetime.timedelta(days=days - 1)
    return [diff(e) for e in human_sends(read_jsonl(LOG)) if edited(e) and parse_date(e.get("at")) >= start]


def current_rules():
    if not RULES.exists():
        return []
    return [m.group(1) for line in RULES.read_text().splitlines() if (m := RULE_RE.match(line))]


def settings():
    learning = load_config().get("learning", {})
    return learning.get("max_learned_rules", 15), learning.get("rule_evidence", 3)


def add_rule(text, why, evidence):
    cap, need = settings()
    text = " ".join(text.split()).rstrip(".")
    sends = {e["id"]: e for e in human_sends(read_jsonl(LOG))}
    real = [i for i in dict.fromkeys(evidence) if i in sends and edited(sends[i])]
    if len(real) < need:
        print(f"error: a rule needs {need} edited sends showing the same change; got {len(real)} "
              f"({', '.join(real) or 'none'}). Wait until the edit repeats.", file=sys.stderr)
        sys.exit(1)
    with locked():
        rules = current_rules()
        if any(normalize(text).lower() in normalize(r).lower() for r in rules):
            return {"added": False, "why": "a rule like this already exists"}
        if len(rules) >= cap:
            print(f"error: at the cap of {cap} rules. Merge two (learn.py retire, then add the merged one) "
                  "or retire a stale one first.", file=sys.stderr)
            sys.exit(1)
        body = RULES.read_text() if RULES.exists() else "# Learned rules\n\n## Rules\n"
        body = re.sub(r"^\s*-\s+\[.*\]\s*$\n?", "", body, flags=re.M)  # drop the template placeholder
        write_text(RULES, body.rstrip("\n") + f"\n- {text}. Why: {why.rstrip('.')}. ({today()}, from {', '.join(real)})\n")
    return {"added": True, "count": len(rules) + 1, "cap": cap}


def retire(fragment):
    with locked():
        if not RULES.exists():
            return {"retired": None}
        lines = RULES.read_text().splitlines(keepends=True)
        hits = [l for l in lines if RULE_RE.match(l) and fragment.lower() in l.lower()]
        if len(hits) != 1:
            print(f"error: {len(hits)} rules match; be more specific", file=sys.stderr)
            sys.exit(1)
        write_text(RULES, "".join(l for l in lines if l is not hits[0]))
    return {"retired": hits[0].strip()}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ingest")
    sub.add_parser("diffs").add_argument("--days", type=int, default=7)
    sub.add_parser("rules")
    p = sub.add_parser("add-rule")
    p.add_argument("text")
    p.add_argument("--why", required=True)
    p.add_argument("--evidence", nargs="+", required=True, help="queue ids of the edited sends")
    sub.add_parser("retire").add_argument("text")
    args = ap.parse_args()
    if args.cmd == "ingest":
        emit(ingest())
    elif args.cmd == "diffs":
        emit(diffs_since(args.days))
    elif args.cmd == "rules":
        cap, need = settings()
        emit({"rules": current_rules(), "count": len(current_rules()), "cap": cap, "evidence_needed": need})
    elif args.cmd == "add-rule":
        emit(add_rule(args.text, args.why, args.evidence))
    elif args.cmd == "retire":
        emit(retire(args.text))


if __name__ == "__main__":
    main()
