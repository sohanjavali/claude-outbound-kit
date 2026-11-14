#!/usr/bin/env python3
"""Deterministic checks on drafts. Hard fails block a draft; warnings don't.

Usage:
  python3 lint.py draft.json          # or pipe JSON on stdin, or pass a JSON string
  python3 lint.py --batch YYYY-MM-DD  # sameness across one day's queue

Draft JSON:
  {"channel": "email"|"linkedin"|"linkedin_connect", "touch": 1, "kind": "new"|"followup"|"reply",
   "subject": "...", "body": "...", "brief": {...}, "their_reply": "..."}
`kind` defaults from touch (1 = new, 2+ = followup). Numbers found anywhere in the brief count as
sourced. Replies skip the length and question rules.
Prints JSON. Exit 0 = pass, 1 = hard fail (or, with --batch, sameness found).
"""

import collections
import re
import sys

from _common import CORE, QUEUE_DIR, die, emit, load_config, md_bullets, read_json_input, read_jsonl, words

DASH_RE = re.compile(r"[—–]|(?<=\S)[ \t]+-{1,2}[ \t]")
HTML_RE = re.compile(r"</?[a-zA-Z][^>]*>")
MD_RE = re.compile(r"(\*\*[^*]+\*\*|__[^_]+__|\[[^\]]+\]\(https?://|^\s*#{1,6}\s|^\s*([-*•]|\d+[.)])\s)", re.M)
URL_RE = re.compile(r"(?:https?://|www\.)\S+|\b[\w-]+\.(?:com|io|co|ai|org|net|app|me)/\S*", re.I)
PLACEHOLDER_RE = re.compile(r"\{\{|\}\}|\{[A-Za-z_ ]+\}|\[[A-Za-z][^\]\n]{0,30}\]")
NUMBER_RE = re.compile(r"(?<![\w./:])(\$)?(\d[\d,]*(?:\.\d+)?)(?![\d/:])\s?"
                       r"(%|percent\b|x\b|k\b|m\b|bn\b|b\b|thousand\b|million\b|billion\b)?", re.I)
UNITS = {"percent": "%", "thousand": "k", "million": "m", "billion": "bn", "b": "bn"}
SOURCED_FIELDS = ("facts", "detail", "proof", "shared_context", "asset")
AI_TELLS = [
    (re.compile(r"\bnot (just|only|merely) [^.?!]{1,40}\bbut\b", re.I), "\"not just X but Y\" construction"),
    (re.compile(r"\b(it's|it is|this is|isn't) (not )?about [^.?!]{1,40}[,;] (it's|it is) about\b", re.I),
     "\"it's not about X, it's about Y\" construction"),
    (re.compile(r"\b(here's the thing|the best part|what stood out|which tells me|i noticed|i came across|"
                r"i saw that you|in short|bottom line|all in all|to sum up|at its core|game-changing)\b", re.I),
     "phrase that reads as generated"),
]


def norm_text(text):
    return (text or "").lower().replace("’", "'").replace("‘", "'")


def phrase_in(phrase, text):
    return re.search(r"(?<![a-z0-9])" + re.escape(phrase) + r"(?![a-z0-9])", text) is not None


def strip_urls(text):
    return URL_RE.sub(" ", text or "")


def load_banned():
    always, first_touch = [], []
    section = always
    path = CORE / "engine" / "banned.txt"
    if not path.exists():
        return always, first_touch
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower() == "[first-touch]":
            section = first_touch
            continue
        section.append(norm_text(line))
    return always, first_touch


def numbers_in(text):
    """Stat-like numbers, with their unit: '5%', '$5m', '5x', '1500'. Years and bare counts up to 10 are ignored."""
    out = set()
    for cur, num, unit in NUMBER_RE.findall(strip_urls(text)):
        num = num.replace(",", "").rstrip(".")
        unit = (unit or "").lower()
        unit = UNITS.get(unit, unit)
        if not num:
            continue
        value = float(num)
        if not cur and not unit and (value <= 10 or (len(num) == 4 and 1900 <= value <= 2100)):
            continue
        out.add(("$" if cur else "") + num + unit)
    return out


def flatten(obj):
    """All string values inside a brief or config, joined, so numbers anywhere in it count as sourced."""
    if isinstance(obj, dict):
        return " ".join(flatten(v) for v in obj.values())
    if isinstance(obj, list):
        return " ".join(flatten(v) for v in obj)
    return str(obj) if obj is not None else ""


def syllables(word):
    w = word.lower().strip("'")
    if len(w) <= 3:
        return 1
    w = re.sub(r"(?:[^laeiouy]es|ed|[^laeiouy]e)$", "", w)
    w = re.sub(r"^y", "", w)
    return max(1, len(re.findall(r"[aeiouy]{1,2}", w)))


def sentences(text):
    return [s for s in re.split(r"(?<=[.!?])\s+|\n+", text) if words(s)]


def grade_level(text):
    ws = [w for w in words(text) if not w.isdigit()]
    if not ws:
        return 0.0
    n_sent = max(1, len(sentences(text)))
    syl = sum(syllables(w) for w in ws)
    return round(0.39 * len(ws) / n_sent + 11.8 * syl / len(ws) - 15.59, 1)


def is_greeting(line):
    return len(words(line)) <= 4 and line.strip().endswith(",")


def split_signoff(body, config=None):
    """(message, sign-off). The sign-off is whatever follows the last question, or a short last line."""
    masked = URL_RE.sub(lambda m: " " * len(m.group(0)), body)  # same length, so indexes still line up
    if "?" in masked:
        idx = masked.rindex("?") + 1
        return body[:idx], body[idx:]
    lines = body.rstrip().split("\n")
    if len(lines) > 1 and len(words(lines[-1])) <= 4:
        return "\n".join(lines[:-1]), lines[-1]
    return body, ""


def limits_for(channel, touch, kind, limits):
    if channel == "linkedin_connect":
        return limits.get("linkedin_connect", {})
    follow = touch > 1 or kind == "followup"
    return (limits.get(f"{channel}_followup") if follow else None) or limits.get(channel, {})


def lint_draft(d, config=None):
    config = config or load_config()
    limits = config.get("limits", {})
    channel = d.get("channel", "email")
    touch = int(d.get("touch") or 1)
    kind = d.get("kind") or ("new" if touch == 1 else "followup")
    subject = d.get("subject") or ""
    body = d.get("body") or ""
    brief = d.get("brief") or {}
    hard, warn = [], []

    if not body.strip():
        return {"pass": False, "hard": ["body is empty"], "warn": [], "words": 0, "grade": 0.0}

    message, tail = split_signoff(body, config)
    n_words = len(words(body))
    q_count = strip_urls(body).count("?")
    lim = limits_for(channel, touch, kind, limits)

    if kind != "reply":
        if channel == "linkedin_connect":
            cap = lim.get("cap_chars")
            if cap and len(body.strip()) > cap:
                hard.append(f"{len(body.strip())} characters, over the connection-note cap of {cap}")
            if q_count > 1:
                hard.append(f"{q_count} question marks, at most one in a connection note")
        else:
            cap, target, low = lim.get("cap_words"), lim.get("target_words"), lim.get("min_words")
            if cap and brief.get("carries"):
                cap += limits.get("carry_bonus_words", 0)
            if cap and n_words > cap:
                hard.append(f"{n_words} words, over the cap of {cap}")
            elif target and n_words > target:
                warn.append(f"{n_words} words, over the {target}-word target")
            floor = limits.get("floor_words", {}).get(channel)
            if floor and n_words < floor:
                warn.append(f"{n_words} words, under the {floor}-word floor (too short reads as a bot)")
            elif low and touch == 1 and n_words < low:
                warn.append(f"{n_words} words, under the {low}-word minimum for a first touch")
            if q_count != 1:
                hard.append(f"{q_count} question marks, needs exactly one")
            else:
                signoff = (config.get("sender") or {}).get("signoff") or ""
                extra = len(words(tail)) - (len(words(signoff)) if signoff and signoff.lower() in tail.lower() else 0)
                if extra > limits.get("signoff_max_words", 6):
                    hard.append("the question isn't at the end (only a sign-off may follow it)")

        if channel == "email" and touch == 1 and not subject.strip():
            hard.append("email first touch needs a subject")
        max_subject = limits.get("subject_max_words", 5)
        if len(words(subject)) > max_subject:
            warn.append(f"subject is {len(words(subject))} words, max {max_subject}")
        if touch == 1 and URL_RE.search(body):
            warn.append("link in a first touch (hurts deliverability)")

        if not any(len(words(s)) <= 5 for s in sentences(message) if not is_greeting(s)):
            warn.append("no sentence of five words or fewer")
        lines = [l for l in message.strip().split("\n") if l.strip()]
        first = lines[1] if lines and is_greeting(lines[0]) and len(lines) > 1 else (lines[0] if lines else "")
        if re.match(r"^\s*I\b", first):
            warn.append("opens with \"I\" (open with their world)")
        for pattern, label in AI_TELLS:
            if pattern.search(message):
                warn.append(label)

    full = subject + "\n" + body
    if PLACEHOLDER_RE.search(full):
        hard.append(f"unfilled placeholder: {PLACEHOLDER_RE.search(full).group(0)}")
    if DASH_RE.search(strip_urls(full)):
        hard.append("dash (use a comma or a period)")
    if HTML_RE.search(full):
        hard.append("HTML tag (plain text only)")
    if MD_RE.search(message):
        hard.append("markdown or a list (plain text only)")

    text = norm_text(strip_urls(full))
    always, first_touch = load_banned()
    for p in always + (first_touch if touch == 1 and kind != "reply" else []):
        if phrase_in(p, text):
            hard.append(f'banned phrase: "{p}"')

    claims_file = CORE / "company" / "claims.md"
    for name in md_bullets(claims_file, "Clients we can't name"):
        if phrase_in(norm_text(name), text):
            hard.append(f'client you can\'t name: "{name}"')
    for phrase in md_bullets(claims_file, "Never say"):
        if phrase_in(norm_text(phrase).strip('"'), text):
            hard.append(f'on the never-say list: "{phrase}"')

    allowed = numbers_in(" ".join(md_bullets(claims_file, "Approved claims")))
    allowed |= numbers_in(flatten({k: brief.get(k) for k in SOURCED_FIELDS})) | numbers_in(d.get("their_reply"))
    allowed |= numbers_in(flatten(config.get("sender")))  # a phone number in the sign-off
    checked = subject + "\n" + body
    for n in sorted(numbers_in(checked) - allowed):
        hard.append(f'number "{n}" isn\'t in claims.md or the brief')

    grade = grade_level(message)
    if kind != "reply":
        if grade > limits.get("reading_grade_fail", 99):
            hard.append(f"reading level about grade {grade}, over {limits['reading_grade_fail']}")
        elif grade > limits.get("reading_grade_warn", 99):
            warn.append(f"reading level about grade {grade}, aim for 6 (rough estimate)")

    return {"pass": not hard, "hard": hard, "warn": warn, "words": n_words, "grade": grade}


STOCK_RE = re.compile(r"\b(my guess is|not sure if|curious whether)\b", re.I)  # meant to repeat


def body_lines(body, config):
    message, _ = split_signoff(body, config)
    lines = [l.strip() for l in message.strip().split("\n") if l.strip()]
    if lines and is_greeting(lines[0]):
        lines = lines[1:]
    return lines


def batch(date, config=None):
    """Openers, closing questions and 4-word phrases shared by too many of one day's drafts."""
    config = config or load_config()
    share = config.get("limits", {}).get("batch_repeat_share", 0.25)
    # First touches only: follow-ups share a deliberate arc, and replies answer different things.
    items = [i for i in read_jsonl(QUEUE_DIR / f"{date}.jsonl") if i.get("kind") == "new" and not i.get("closed")]
    out = {"date": date, "items": len(items), "shared_openers": [], "shared_closers": [],
           "repeated_phrases": [], "flagged_ids": []}
    if len(items) < 5:
        return out
    limit = max(3, int(share * len(items)) + 1)
    openers, closers, grams = (collections.defaultdict(list) for _ in range(3))
    for it in items:
        lines = body_lines(it["body"], config)
        if not lines:
            continue
        text = STOCK_RE.sub("", " ".join(lines))
        openers[" ".join(w.lower() for w in words(lines[0])[:4])].append(it["id"])
        last = sentences(text)[-1] if sentences(text) else ""
        closers[" ".join(w.lower() for w in words(last))].append(it["id"])
        ws = [w.lower() for w in words(text)]
        for g in {" ".join(ws[i:i + 4]) for i in range(len(ws) - 3)}:
            grams[g].append(it["id"])
    flagged = set()
    for key, found in (("shared_openers", openers), ("shared_closers", closers), ("repeated_phrases", grams)):
        for text, ids in sorted(found.items(), key=lambda kv: -len(kv[1])):
            if text and len(ids) >= limit:
                out[key].append({"text": text, "ids": ids})
                flagged.update(ids[1:])  # keep one, rewrite the rest
    out["repeated_phrases"] = out["repeated_phrases"][:10]
    out["flagged_ids"] = sorted(flagged)
    return out


def main():
    args = sys.argv[1:]
    if args and args[0] in ("-h", "--help"):
        print(__doc__)
        return
    if args and args[0] == "--batch":
        if len(args) < 2:
            die("--batch needs a date (YYYY-MM-DD)")
        result = batch(args[1])
        emit(result)
        sys.exit(1 if result["flagged_ids"] else 0)
    draft = read_json_input(args[0] if args else None)
    if not isinstance(draft, dict):
        die("draft must be a JSON object")
    result = lint_draft(draft)
    emit(result)
    sys.exit(0 if result["pass"] else 1)


if __name__ == "__main__":
    main()
