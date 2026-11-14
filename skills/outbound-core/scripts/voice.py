#!/usr/bin/env python3
"""The voice bank: real messages the sender wrote, which the writer matches (never copies).

Usage:
  python3 voice.py build sent.jsonl                       # onboarding: clean 20+ sent emails, seed the bank
  python3 voice.py import-linkedin messages.csv --me "Full Name"   # from LinkedIn's data export
  python3 voice.py pick --channel email [--touch 1] [--angle A] [--segment S] [--query "words"]
                        [--seed LEAD_ID] [--n 5] [--replied]
  python3 voice.py add '{"channel": ..., "body": ...}'
  python3 voice.py stats

sent.jsonl has one sent email per line: {"subject", "body", "to", "date", "got_reply": true|false}.
"""

import argparse
import collections
import csv
import hashlib
import re
import statistics

from _common import (CORE, EXAMPLES, die, emit, load_config, locked, normalize, now, read_json_input, read_jsonl,
                     words, write_jsonl)

CORPUS = CORE / "person" / "sent-corpus.jsonl"
MIN_WORDS, MAX_WORDS = 15, 150
QUOTE_START = re.compile(r"^(On .+wrote:|-----Original Message-----|From: .+|Sent from my \w+)", re.I)
NOT_OUTREACH = re.compile(r"\b(invoice|receipt|password|unsubscribe|out of office|calendar|invitation:|accepted:|"
                          r"declined:|order #|tracking number|zoom\.us|meet\.google)\b", re.I)


def clean(body):
    """Drop quoted replies and the signature block; keep what the sender actually typed."""
    kept = []
    for line in (body or "").replace("\r\n", "\n").split("\n"):
        if QUOTE_START.match(line.strip()) or line.strip() in ("--", "-- "):
            break
        if line.lstrip().startswith(">"):
            continue
        kept.append(line.rstrip())
    return re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip()


def opener(body):
    lines = [l for l in body.strip().split("\n") if l.strip()]
    if lines and len(words(lines[0])) <= 4 and lines[0].strip().endswith(","):
        lines = lines[1:]
    return " ".join(w.lower() for w in words(lines[0])[:4]) if lines else ""


def profile(rows):
    bodies = [r["body"] for r in rows]
    if not bodies:
        return None
    lengths = [len(words(b)) for b in bodies]
    sentences = [len(words(s)) for b in bodies for s in re.split(r"[.!?]+\s", b) if words(s)]
    return {
        "messages": len(rows),
        "median_words": statistics.median(lengths),
        "median_sentence_words": statistics.median(sentences) if sentences else 0,
        "share_with_a_question": round(sum("?" in b for b in bodies) / len(bodies), 2),
        "share_with_exclamation": round(sum("!" in b for b in bodies) / len(bodies), 2),
        "common_greetings": collections.Counter(b.split("\n", 1)[0].strip()[:20] for b in bodies).most_common(5),
        "common_signoffs": collections.Counter(b.strip().split("\n")[-1].strip() for b in bodies).most_common(5),
    }


def keep(body, subject=""):
    n = len(words(body))
    return MIN_WORDS <= n <= MAX_WORDS and not NOT_OUTREACH.search(subject + " " + body)


def seed_bank(rows, channel):
    with locked():
        bank = [x for x in read_jsonl(EXAMPLES) if not (x.get("source") == "sent-mail" and x.get("channel") == channel)]
        seeds = [{"source": "sent-mail", "channel": channel, "subject": r.get("subject", ""), "body": r["body"],
                  "got_reply": bool(r.get("got_reply")), "added": now()} for r in rows]
        write_jsonl(EXAMPLES, seeds + bank)
        corpus = [r for r in read_jsonl(CORPUS) if r.get("channel", "email") != channel]
        write_jsonl(CORPUS, corpus + [dict(r, channel=channel) for r in rows])


def build(path):
    raw = read_jsonl(path)
    if not raw:
        die(f"no messages in {path}")
    rows, seen = [], set()
    for r in raw:
        body = clean(r.get("body", ""))
        key = normalize(body).lower()
        if not keep(body, r.get("subject", "")) or key in seen:
            continue
        seen.add(key)
        rows.append({"subject": r.get("subject", ""), "body": body, "date": r.get("date"),
                     "got_reply": bool(r.get("got_reply"))})
    seed_bank(rows, "email")
    out = {"kept": len(rows), "dropped": len(raw) - len(rows), "with_reply": sum(r["got_reply"] for r in rows),
           "profile": profile(rows)}
    if len(rows) < 20:
        out["warning"] = (f"only {len(rows)} usable messages; 20 or more gives a better voice. "
                          "Ask the user to paste 10 to 20 more messages they wrote.")
    emit(out)


def import_linkedin(path, me):
    """LinkedIn's export (messages.csv): the sender's own messages, and whether the other person wrote back."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = [{k.strip().lower(): (v or "") for k, v in r.items() if k} for r in csv.DictReader(f)]
    if not rows or "content" not in rows[0]:
        die("this doesn't look like LinkedIn's messages.csv (no CONTENT column)")
    me = me.strip().lower()
    convos = collections.defaultdict(list)
    for r in rows:
        convos[r.get("conversation id", "")].append(r)
    kept, seen = [], set()
    for msgs in convos.values():
        msgs.sort(key=lambda r: r.get("date", ""))
        for i, r in enumerate(msgs):
            if r.get("from", "").strip().lower() != me:
                continue
            body = clean(r.get("content", ""))
            key = normalize(body).lower()
            if key in seen or not (8 <= len(words(body)) <= MAX_WORDS):
                continue
            seen.add(key)
            replied = any(m.get("from", "").strip().lower() != me for m in msgs[i + 1:])
            kept.append({"subject": "", "body": body, "date": r.get("date"), "got_reply": replied})
    if not kept:
        die(f'no messages from "{me}" found; use your name exactly as it appears in the FROM column')
    seed_bank(kept, "linkedin")
    emit({"kept": len(kept), "with_reply": sum(k["got_reply"] for k in kept), "profile": profile(kept)})


def cap_for(channel, touch, config):
    limits = config.get("limits", {})
    base = "linkedin" if channel.startswith("linkedin") else "email"
    lim = (limits.get(f"{base}_followup") if touch and touch > 1 else None) or limits.get(base, {})
    return (lim.get("cap_words") or 120) + limits.get("carry_bonus_words", 25)


def pick(channel, touch, angle, segment, n, replied_only=False, query=None, seed=None):
    config = load_config()
    family = "linkedin" if channel.startswith("linkedin") else "email"
    bank = [x for x in read_jsonl(EXAMPLES) if x.get("body") and not x.get("auto")]
    if replied_only:
        bank = [x for x in bank if x.get("got_reply")] or bank
    cap = cap_for(channel, touch, config)
    pool = [x for x in bank if x.get("channel", "email") == family and len(words(x["body"])) <= cap]
    if len(pool) < n:
        pool += [x for x in bank if x not in pool and len(words(x["body"])) <= cap]
    terms = {w.lower() for w in words(query or "") if len(w) > 3}

    def score(i, x):
        s = 4 * bool(x.get("got_reply")) + 2 * (x.get("source") == "kit-sent")
        s += 2 * bool(angle and x.get("angle") == angle) + bool(segment and x.get("segment") == segment)
        if touch:
            s += 2 * (((x.get("touch") or 1) > 1) == (touch > 1))
        s += min(3, len(terms & {w.lower() for w in words(x["body"])}))
        tie = int(hashlib.md5(f"{seed}:{i}".encode()).hexdigest(), 16) % 1000 / 1000 if seed else -i / 10 ** 6
        return s + tie

    picked, openers = [], set()
    for i, x in sorted(enumerate(pool), key=lambda p: score(*p), reverse=True):
        o = opener(x["body"])
        if o in openers:
            continue
        openers.add(o)
        picked.append({"subject": x.get("subject", ""), "body": x["body"], "got_reply": bool(x.get("got_reply"))})
        if len(picked) == n:
            break
    return picked


def add(example):
    if not example.get("body"):
        die("example needs a body")
    example.setdefault("source", "kit-sent")
    example.setdefault("added", now())
    cap = load_config().get("learning", {}).get("max_examples", 200)
    with locked():
        bank = read_jsonl(EXAMPLES)
        key = normalize(example["body"]).lower()
        if any(normalize(x.get("body", "")).lower() == key for x in bank):
            return {"added": False, "why": "already in the bank", "bank_size": len(bank)}
        bank.append(example)
        while len(bank) > cap:
            # The oldest kit-sent example goes first; the sender's own mail goes last.
            idx = next((i for i, x in enumerate(bank) if x.get("source") != "sent-mail"), 0)
            bank.pop(idx)
        write_jsonl(EXAMPLES, bank)
    return {"added": True, "bank_size": len(bank)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build").add_argument("path")
    p = sub.add_parser("import-linkedin")
    p.add_argument("path")
    p.add_argument("--me", required=True, help="your name exactly as LinkedIn shows it")
    p = sub.add_parser("pick")
    p.add_argument("--channel", default="email", choices=["email", "linkedin", "linkedin_connect"])
    p.add_argument("--touch", type=int)
    p.add_argument("--angle")
    p.add_argument("--segment")
    p.add_argument("--query", help="words from the brief, to favour examples on a similar topic")
    p.add_argument("--seed", help="the lead id, so different leads get different examples")
    p.add_argument("--n", type=int, default=5)
    p.add_argument("--replied", action="store_true", help="only examples that got a reply, if any")
    sub.add_parser("add").add_argument("json", nargs="?")
    sub.add_parser("stats")
    args = ap.parse_args()

    if args.cmd == "build":
        build(args.path)
    elif args.cmd == "import-linkedin":
        import_linkedin(args.path, args.me)
    elif args.cmd == "pick":
        emit(pick(args.channel, args.touch, args.angle, args.segment, args.n, args.replied, args.query, args.seed))
    elif args.cmd == "add":
        emit(add(read_json_input(args.json)))
    elif args.cmd == "stats":
        bank = read_jsonl(EXAMPLES)
        emit({"bank_size": len(bank), "by_source": dict(collections.Counter(x.get("source") for x in bank)),
              "with_reply": sum(bool(x.get("got_reply")) for x in bank), "profile": profile(bank)})


if __name__ == "__main__":
    main()
