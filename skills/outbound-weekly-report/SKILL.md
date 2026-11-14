---
name: outbound-weekly-report
description: Writes the weekly outbound report. Replies, positive replies, meetings, kills and edit rate by angle, segment and warmth tier, plus failed or missed runs, learned-rule upkeep, autonomy-ladder advice and when to raise volume. Use when the user says "write the weekly outbound report", "how's outbound doing", "outbound numbers this week", or a scheduled task asks for it.
model: sonnet
---

# Outbound weekly report

`$CORE` is the `outbound-core` folder next to this skill's folder (usually `~/.claude/skills/outbound-core/`). Read `$CORE/config.json` and `$CORE/engine/autonomy.md` first. If the prompt says this is a scheduled run, don't stop to ask questions. Never change `config.json` yourself: recommend, and let the human decide. If anything breaks, follow "If something breaks" in `$CORE/SKILL.md`.

## 1. Pull the numbers
- `python3 "$CORE/scripts/log.py" report --days 7 --json`, and `--days 28` for the trend.
- `python3 "$CORE/scripts/edit_rate.py" --days 7 --by segment`, and the same with `--by angle`.
- `python3 "$CORE/scripts/edit_rate.py" --ladder`.
- `python3 "$CORE/scripts/log.py" runs --days 7`. Compare against the schedule in config to find runs that failed or never happened. A skill whose `schedule` entry is `"off"` isn't scheduled, so its runs are never missed: don't report them.
- `python3 "$CORE/scripts/learn.py" diffs --days 28` and `learn.py rules`.
- `python3 "$CORE/scripts/review_queue.py" summary`, for decisions still waiting.

## 2. Tend the learned rules
Read the diffs and look for the same edit in three or more sends: a greeting they always change, a phrase they always cut, a sentence they always shorten.
- For each new pattern: `learn.py add-rule "<rule>" --why "<what the edits show>" --evidence <id> <id> <id>`.
- Merge rules that overlap (retire both, add one), and retire rules the recent edits no longer support.
- A rule a script could check (an exact phrase) belongs in `$CORE/engine/banned.txt`. Add it there and retire the rule.

Aim for fewer rules each month, not more.

## 3. Write the report
Save it by piping the text to `python3 "$CORE/scripts/kit_write.py" state/reports/<today>.md` (Claude Code protects `~/.claude/` from direct file writes, so always save through the script). The top section is under ten lines:

1. **This week:**
   - first touches and follow-ups sent
   - replies, positive replies and meetings
   - drafts killed in review
2. **Runs:** any scheduled run that failed or didn't happen (the computer was probably asleep), and anything still unconfirmed (`log.py unconfirmed`).
3. **What's working:** the best and worst angle, segment and tier by positive replies per send.
   - Under 30 sends: say "too early" rather than ranking it.
   - Before dropping a segment or angle, it's worth waiting for a couple hundred sends in it. That's a recommendation, not a rule.
4. **Edits:** the share of reviewed drafts sent untouched, and the share killed, overall and by segment, with the trend. Mention rules added, merged or retired.
5. **Autonomy:** from `--ladder`.
   - Segments eligible to move up: recommend it, and say the user decides by adding `"<segment>": 3` to `autonomy.segments`.
   - Segments that must move down: say so plainly, and ask the human to remove them from `autonomy.segments`.
6. **Volume and sending:**
   - **Raising volume:** if decisions are being cleared daily and edits are getting lighter, suggest raising `volume.new_leads_per_day` by 5 to 10.
   - **The cap:** remind them that each new lead becomes about `sequence.max_touches` sends over the following days, so `volume.max_sends_per_day` is the real ceiling.
   - **Separate domain:** if daily sends pass `deliverability.separate_domain_above_per_day`, recommend a separate warmed domain before going higher.
7. **Watch:**
   - bounces and unsubscribes
   - decisions left waiting in older queues
   - LinkedIn check-ins nobody answered

Don't list settings the user left blank (`booking_link`, `sender.company`) as things to fix: some people choose not to have them. Mention a blank `booking_link` only if a positive reply came in this week, and then in one line.

## 4. Share it
- Show the report in chat.
- Put a three-line summary at the top of today's review file with `review_queue.py note "<summary>; full report in state/reports/<today>.md"`, so it's seen even when this ran unattended.
- `python3 "$CORE/scripts/log.py" run weekly-report ok`.

Based on the public playbook design.
