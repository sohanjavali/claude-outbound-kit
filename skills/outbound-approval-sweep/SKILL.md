---
name: outbound-approval-sweep
description: Sends what the human approved in the outbound review queue (plus auto-approved items), never twice and never over the daily cap, logs each send to the CRM with the next task, records kills and finished tasks, and adds sent messages to the voice bank. Use when the user says "run the outbound approval sweep", "send the approved drafts", "send what I approved", "I'm done reviewing", "I approved the queue", or a scheduled task asks for it.
model: sonnet
---

# Outbound approval sweep

`$CORE` is the `outbound-core` folder next to this skill's folder (usually `~/.claude/skills/outbound-core/`). Read `$CORE/config.json` first. If anything breaks, follow "If something breaks" in `$CORE/SKILL.md`.

This runs every 30 minutes, and sometimes a manual run overlaps a scheduled one. The scripts make that safe, as long as you follow the claim step exactly. If the prompt says this is a scheduled run, don't stop to ask questions.

## 1. Finish anything a crashed run left
`python3 "$CORE/scripts/log.py" unconfirmed` lists sends claimed more than 15 minutes ago and never confirmed (younger claims may belong to a run still sending, so leave them alone). For each one, search the Sent folder (the Drafts folder in `draft` mode) for that message:
- **Found:** log it as sent (step 3) and mark it.
- **Not found:** `log.py release <id>`, so it can go out this sweep.

## 2. Collect decisions
`python3 "$CORE/scripts/review_queue.py" parse`. It reads every open queue from the last two weeks, not just today's. It returns items the human decided on, plus items marked `auto`, with their edited subject and body, a fresh lint result, and a `blocked` reason if the thread changed since the draft was made.

Also run `review_queue.py summary`. If it lists `unrecognized_statuses`, write a note at the top of the review file listing those ids and the accepted words (✅, ❌, sent).

## 3. Act on each item
Pipe JSON to `log.py add` on stdin.

- **`blocked` is set:** don't send. `review_queue.py close <id> "blocked: <reason>"`. That frees the thread, so the next touch or a fresh draft can come along later.
- **kill:** log it with the item's fields, so edit rates count it:
  ```json
  {"event": "killed", "id": "...", "email": "...", "touch": N, "channel": "...", "kind": "...",
   "segment": "...", "angle": "...", "tier": "...", "spot_check": false}
  ```
  Then `mark <id> killed`. Killing a follow-up ends that sequence.
- **Task, intro (✅ or done):** log `{"event": "intro", "via": "<via>", "email": "<the lead's email, if known>", "name": "<the lead's name>"}` and `mark <id> done`. On ❌, `mark <id> skipped`.
- **Task, other (✅, done or ❌):** `mark <id> done`. These are reminders the human handles themselves.
- **Task, LinkedIn check-in:**
  - ✅ means they replied: log `{"event": "reply", "email": "...", "channel": "linkedin", "category": "other"}`, and tell the human to answer it on LinkedIn.
  - ❌ means no reply: log `{"event": "checkin", "email": "...", "channel": "linkedin", "replied": false}`.
  - Either way, `mark <id> done`.
- **LinkedIn draft, approved:** the kit never sends LinkedIn. `mark <id> "approved, send by hand on LinkedIn, then set status to sent"`.
- **LinkedIn draft, status `sent`:** the human sent it by hand. Log it as sent with `"mode": "manual"`, then `mark <id> sent`.
- **Email, approve or auto:**
  1. If `lint.pass` is false (the human's edit broke a rule), don't send. `mark <id> "blocked by lint: <first error>. Fix it and set status to ✅ again"`.
  2. `python3 "$CORE/scripts/log.py" claim <id>`.
     - `ok` false with "cap": stop sending for today and leave the rest for tomorrow's sweep.
     - `ok` false for any other reason: skip the item.
  3. Send it from the connected email account. A follow-up or a reply goes as a reply in `thread_id`, keeping the subject. If `email_send_mode` is `draft`, create a draft instead. Keep the `thread_id` and `message_id` the connector returns.
  4. If the send failed, `log.py release <id>`. Don't mark it: the next sweep retries.
  5. Log it:
     ```json
     {"event": "sent", "id": "...", "email": "...", "name": "...", "company": "...", "lead_id": "...",
      "channel": "email", "touch": N, "kind": "new|followup|reply", "tier": "...", "segment": "...",
      "angle": "...", "rung": "<brief.rung>", "subject": "...", "body": "<what was sent>",
      "draft": "<original_body>", "thread_id": "...", "message_id": "...",
      "mode": "send|draft|auto", "spot_check": false}
     ```
     Use `mode: auto` when the decision was `auto`. Use `spot_check: true` when the item was a spot check the human approved.
  6. `review_queue.py mark <id> sent` (or `drafted`).
  7. **CRM** (skip if `crm` is `none`), following `$CORE/company/crm.md`: create or update the contact, log the exact message, and create the next task dated by `log.py next-due <id>` (none when `next_touch` is null). In `draft` mode, skip the task: the email hasn't gone out yet, so follow-ups adds the task once it sees the real send. In a scheduled run, queue it instead of writing to the CRM (see "CRM writes" in `$CORE/SKILL.md`), with exactly these fields piped to `crm_queue.py add`:
     ```json
     {"action": "send", "ref": "<queue id>", "email": "...", "name": "...", "company": "...", "title": "...",
      "subject": "...", "body": "<what was sent>", "thread_id": "...", "message_id": "...",
      "next_task_due": "<from log.py next-due, or omit when next_touch is null>", "next_task_name": "Touch N follow-up: <company>",
      "do": "<the same changes in plain words>"}
     ```
     Queued CRM updates are not a failure: the run is still `ok`.

In `draft` mode, the log records what went into the drafts folder. Edits the human makes in the email app aren't seen, and follow-ups check that the previous touch was actually sent first.

## 4. Learn
`python3 "$CORE/scripts/learn.py" ingest`. Sent messages join the example bank, and examples whose message later got a reply are marked so they rank first. Don't add rules here: the weekly report does that once an edit has repeated three times.

## 5. Finish
- `python3 "$CORE/scripts/log.py" run approval-sweep ok "sent N, killed M"`. Use `partial` or `failed` with the reason if something broke, and add a `review_queue.py note`.
- **Summary:** sent, drafted, killed, blocked (with reasons), held by the daily cap, and still waiting for a decision. If `crm_queue.py pending --count` is above zero, end with "N CRM updates waiting. Say 'sync my CRM' to apply them." If nothing was decided, say so in one line.

Based on the public playbook design.
