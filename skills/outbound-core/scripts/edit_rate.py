#!/usr/bin/env python3
"""How much the human changes drafts before they go out, and what that means for the autonomy ladder.

Usage:
  python3 edit_rate.py [--days 7] [--by angle|segment|tier|channel]
  python3 edit_rate.py --ladder      # segments that qualify to move up, and ones that must move down

Every draft the human reviewed is untouched (sent as drafted), light (small edits), heavy, or killed.
Killed drafts count against a segment: killing half and sending the rest untouched isn't 100%.
Auto-sent drafts nobody reviewed are left out.
"""

import argparse
import datetime
import difflib

from _common import LOG, emit, load_config, normalize, parse_date, read_jsonl

LIGHT_EDIT_RATIO = 0.85
BANDS = ("untouched", "light", "heavy", "killed")


def classify(e):
    if e.get("event") == "killed":
        return "killed"
    a, b = normalize(e.get("draft", "")), normalize(e.get("body", ""))
    if a == b:
        return "untouched"
    return "light" if difflib.SequenceMatcher(None, a, b).ratio() >= LIGHT_EDIT_RATIO else "heavy"


def reviewed(events, start=None, end=None):
    """Drafts a human decided on: sent ones (not auto, not replies) and killed ones."""
    out = []
    for e in events:
        ev = e.get("event")
        if e.get("kind") == "reply" or (ev == "sent" and ("draft" not in e or e.get("mode") == "auto")):
            continue
        if ev not in ("sent", "killed"):
            continue
        d = parse_date(e.get("at"))
        if (start and d < start) or (end and d > end):
            continue
        out.append(e)
    return out


def stats(events, by=None):
    groups = {}
    for e in events:
        key = str(e.get(by) or "unknown") if by else "all"
        g = groups.setdefault(key, {"reviewed": 0, **{b: 0 for b in BANDS}})
        g["reviewed"] += 1
        g[classify(e)] += 1
    for g in groups.values():
        g["untouched_rate"] = round(g["untouched"] / g["reviewed"], 2) if g["reviewed"] else None
    return groups


def ladder(events, config, today=None):
    rules = config.get("autonomy", {})
    promote = rules.get("promote_after", {})
    weeks = promote.get("weeks", 3)
    need_rate = promote.get("untouched_rate", 0.8)
    need_sends = promote.get("min_sends", 30)
    demote_above = rules.get("demote_if_spot_edit_rate_above", 0.3)
    default = rules.get("default_level", 2)
    levels = rules.get("segments", {})
    today = today or datetime.date.today()

    seen = reviewed(events)
    eligible = []
    for seg in sorted({e.get("segment") or "unknown" for e in seen}):
        if levels.get(seg, default) >= 3:
            continue
        mine = [e for e in seen if (e.get("segment") or "unknown") == seg]
        weekly, total = [], 0
        for w in range(weeks):
            end = today - datetime.timedelta(days=7 * w)
            s = stats(reviewed(mine, end - datetime.timedelta(days=6), end)).get("all", {"reviewed": 0, "untouched_rate": None})
            weekly.append(s["untouched_rate"])
            total += s["reviewed"]
        if total >= need_sends and all(r is not None and r >= need_rate for r in weekly):
            eligible.append({"segment": seg, "reviewed": total, "weekly_untouched_rate": weekly})

    week = reviewed(events, today - datetime.timedelta(days=6), today)
    demote = []
    for seg, level in levels.items():
        if level < 3:
            continue
        checks = [e for e in week if e.get("segment") == seg and e.get("spot_check")]
        if checks:
            changed = sum(1 for e in checks if classify(e) != "untouched")
            rate = round(changed / len(checks), 2)
            if rate > demote_above:
                demote.append({"segment": seg, "level": level, "spot_checks": len(checks), "changed_rate": rate})
    return {"eligible_to_move_up": eligible, "must_move_down": demote}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--by", choices=["angle", "segment", "tier", "channel"])
    ap.add_argument("--ladder", action="store_true")
    args = ap.parse_args()
    events = read_jsonl(LOG)
    if args.ladder:
        emit(ladder(events, load_config()))
        return
    emit(stats(reviewed(events, datetime.date.today() - datetime.timedelta(days=args.days - 1)), args.by))


if __name__ == "__main__":
    main()
