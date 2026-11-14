---
name: outbound-followups
description: Drafts the next touch for every outbound thread that's due, after re-checking holds, replies and fresh news, and queues LinkedIn check-ins before any LinkedIn follow-up. Use when the user says "draft today's outbound follow-ups", "run follow-ups", "who's due for a follow-up", or a scheduled task asks for it.
model: sonnet
---

# Outbound follow-ups

`$CORE` is the `outbound-core` folder next to this skill's folder (usually `~/.claude/skills/outbound-core/`). Read `$CORE/config.json`, `$CORE/engine/sequence.md` and `$CORE/engine/pipeline.md` first. If anything breaks, follow "If something breaks" in `$CORE/SKILL.md`.

If the prompt says this is a scheduled run, don't stop to ask questions.

## 1. Draft mode: record what actually went out
Only if `email_send_mode` is `draft`. Approved emails sit in the Drafts folder until the human sends them, and follow-ups must count from that moment.

1. `python3 "$CORE/scripts/log.py" undelivered` lists drafts not yet seen in the Sent folder.
2. For each, open its thread by `thread_id` first: a message you sent in that thread after `drafted_at` is the send, even if the human changed the To address or subject before sending. Only with no `thread_id`, or no such message in the thread, search the Sent folder by recipient and subject.
3. If it's there, log when it really went out:
   ```json
   {"event": "delivered", "id": "<queue id>", "at": "<the sent message's date, ISO>", "message_id": "...", "thread_id": "..."}
   ```
   piped to `log.py add`. Follow-up replies go in this real thread.
   Then the CRM's next-touch task (skip if `crm` is `none`): `log.py next-due <queue id>` gives the date, counted from the real send. Create the task named as in `crm.md` for that date, or in a scheduled run queue it with `crm_queue.py add` (`"action": "task"`, `"ref": "<queue id>"`, `next_task_due` and `next_task_name` set). No task when `next_touch` is null.
4. If a draft is still unsent after 3 days, mention it in the summary.

Until a draft is delivered, its thread isn't due for a follow-up.

## 2. Who's due
`python3 "$CORE/scripts/log.py" due`. It lists threads, one per person and channel, that meet all of these:
- the next touch's day has come (`sequence.spacing_days`)
- no reply, meeting, bounce or stop
- under `sequence.max_touches`
- nothing for that touch already waiting in a queue

Overdue ones come first.

## 3. LinkedIn check-ins first
For each item with `needs_checkin: true`, don't draft. The kit can't see LinkedIn replies, so queue a check-in for the human:

```json
{"lead": {"name": "...", "email": "...", "company": "...", "linkedin": "..."}, "task_type": "linkedin_checkin",
 "channel": "linkedin", "task": "Did Dana Reyes reply on LinkedIn since <last_sent date>?"}
```

Pipe it to `python3 "$CORE/scripts/review_queue.py" task`. Once the human answers in the review file and the sweep logs the answer, the thread shows up here again. If the last touch was a connection note (`last_channel` is `linkedin_connect`), word the task "Did Dana Reyes accept your connection request and reply?". If they never accepted, there's no LinkedIn touch 2: ask the human to answer ❌, and log `{"event": "stop", "email": "...", "reason": "connection not accepted"}` once they confirm.

## 4. For each email thread (and each LinkedIn thread that's been checked)
1. **Re-run the hold checks.** If any of these now applies, log `{"event": "stop", "email": "...", "reason": "..."}` (piped to `log.py add`), close the CRM task (in a scheduled run, queue it with `crm_queue.py add`, `"action": "stop"`), and skip the thread:
   - `log.py seen <email>` shows never-contact
   - an open deal now exists
   - another rep has started talking to them
2. **Check for replies.** Search the inbox for anything from that address, or anyone at their domain, since the last touch. If there's a reply, don't draft: reply triage handles it.
3. **Check for news.** A quick search for news about them or their company since the last touch. New, sourced news can be the fact for this touch.
4. **Draft** with the pipeline in `$CORE/engine/pipeline.md`, batching two or three threads per subagent call:
   - Research covers only what's new since the last touch.
   - The selector gets the touch number, the arc row from `sequence.md`, `previous_touches`, and the previous angle and `rung` from the `due` output. It follows the offer ladder: never the same rung twice in a row, never three gives in a row.
   - Touch 2 gives something real (often a value asset from `company/offer.md`). Touch 3 brings the product in, with an easy-out interest question.
   - Writer examples: `voice.py pick --channel <channel> --touch <next_touch> --seed <lead id> ...`.
5. **Queue** with `python3 "$CORE/scripts/review_queue.py" add`. In full mode the drafting stages run as subagents, never inline, and the queue refuses a draft without the judge's result. Use the same fields as the daily batch, plus:
   - `"kind": "followup"`
   - `"touch": <next_touch>`
   - `"channel"`, `"thread_id"` and `"subject"` from the `due` output (LinkedIn follow-ups are always `linkedin`, even after a connection note)

## 5. Batch sameness
`python3 "$CORE/scripts/lint.py" --batch <today>`, and rewrite the flagged ones as the daily batch does.

## 6. Finish
- `python3 "$CORE/scripts/log.py" run followups ok "queued N"`. Use `partial` or `failed` with the reason, plus a `review_queue.py note`, if something broke.
- **Summary:** follow-ups queued by touch number, LinkedIn check-ins queued, threads stopped and why, threads skipped because a reply came in, and anything overdue.

Based on the public playbook design.
