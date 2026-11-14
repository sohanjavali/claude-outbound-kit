---
name: outbound-reply-triage
description: Reads replies to outbound messages (including from colleagues at the same company), sorts them, stops sequences, drafts answers, queues the booking link on a yes, turns referrals into warm drafts the same day, and logs bounces and booked meetings. Use when the user says "triage outbound replies", "check my outbound replies", "any replies?", or a scheduled task asks for it.
model: sonnet
---

# Outbound reply triage

`$CORE` is the `outbound-core` folder next to this skill's folder (usually `~/.claude/skills/outbound-core/`). Read `$CORE/config.json` first. If anything breaks, follow "If something breaks" in `$CORE/SKILL.md`.

If the prompt says this is a scheduled run, don't stop to ask questions.

## 1. Find new replies
1. **Window:** find the last successful run with `python3 "$CORE/scripts/log.py" runs --days 30 --skill reply-triage`. Search from one day before it, or from the last 7 days if there isn't one. A wide window is safe, because already-logged messages are skipped.
2. **Who:** everyone sent a message in the last 60 days, from the sent events in `$CORE/state/outreach-log.jsonl`. Also include anyone else at their company domain, since replies often come from a colleague or an alias (skip free-mail domains like gmail.com).
3. **Search** the inbox for messages from those addresses and domains in the window. Batch them into a few searches by domain rather than one per person. Also look for:
   - bounce notices that mention those addresses
   - booking confirmations from the scheduling tool (Cal.com, Calendly or similar)
4. **Skip** any message already logged: `python3 "$CORE/scripts/log.py" has <message_id>`.

## 2. Sort each reply

| Category | Means |
|---|---|
| `positive` | Interested, wants to talk, asks how to start |
| `engaged` | Answers our question or keeps talking, with no clear yes, no or question back. The most common reply to a first touch |
| `question` | Asks something before deciding |
| `referral` | Points to someone else |
| `not-now` | Interested later, or bad timing |
| `not-interested` | A clear no |
| `unsubscribe` | Asks not to be contacted |
| `ooo` | Automatic out-of-office |
| `other` | Anything else, with nothing to pick up (an automatic reply that isn't out-of-office, a blank reply) |

Log it by piping to `log.py add`:

```json
{"event": "reply", "email": "<who we wrote to>", "category": "...", "channel": "email",
 "message_id": "...", "thread_id": "..."}
```

For a reply from a colleague, log it against the person we wrote to, and mention the colleague in the summary. For `ooo`, add `"back_on": "YYYY-MM-DD"` if it gives a return date. A reply event of any category except `ooo` ends that person's sequences.

## 3. Act

| Category | Draft | CRM (skip if `crm` is `none`) |
|---|---|---|
| `positive` | A short reply with `booking_link`. Queue it with `"priority": true` and `"booking_only": true` if it does nothing but share the link | Per `crm.md` → "On a reply" |
| `engaged` | A short reply that picks up what they said: one sentence on their answer, then one easy question that moves toward the problem the offer solves. If they've described exactly that problem, offer to show them in one line instead. No booking link unless they ask. Priority | Update |
| `question` | Answer using only `offer.md` and `claims.md`, ending with one question. If the files can't answer it, queue a task for the human instead of guessing. Priority | Update |
| `referral` | A short thank-you to the person who replied (priority). Then the referred person gets a same-day warm draft (see below) | Update |
| `not-now` | A one-line acknowledgment | A task to revisit at the time they named. With no CRM, note the date in the summary |
| `not-interested` | None | Per `crm.md` |
| `unsubscribe` | None. Add the email to `crm.md` → "Never contact" | Do not contact |
| `ooo` | None. The next touch waits until they're back | None |

In a scheduled run, every CRM change in this table and below goes to `crm_queue.py add` (`"action"` is `reply`, `bounce` or `task`, `"ref"` is their message_id) instead of a CRM write. See "CRM writes" in `$CORE/SKILL.md`.

**Other events:**
- **Bounce:** log `{"event": "bounce", "email": "...", "message_id": "..."}` and mark the email invalid in the CRM.
- **Booking confirmation:** log `{"event": "meeting", "email": "...", "message_id": "..."}`. This also ends the sequence.

**Referrals, the same day:** look up the referred person through Apollo, verified emails only, and run `log.py seen <email>` (with `lead_source` `paste`, skip the lookup and queue the task below). Ignore `colleagues_contacted_recently` (the colleague sent us to them), but respect every other hold. If they pass, run the pipeline as tier A, with `shared_context` naming who pointed us to them, and queue it with `"priority": true` and `"referral": true`. If they can't be found or verified, queue a task with what you know (`"task_type": "other"`).

**Queueing reply drafts:** use `python3 "$CORE/scripts/review_queue.py" add` with:
- the `lead` and `channel` from their last sent touch
- `"touch"` set to that touch's number
- `"kind": "reply"`, `"reply_to": "<their message_id>"`, `"thread_id"` and `"subject"`
- `"their_reply"` set to the text of their message

Reply drafts never send on their own, except a booking-link-only reply in a segment at autonomy level 4. The queue decides that.


## 4. Finish
- `python3 "$CORE/scripts/log.py" run reply-triage ok "N replies"`. Use `partial` or `failed` with the reason, plus a `review_queue.py note`, if a search or connector failed.
- **Summary:** if CRM updates are waiting (`crm_queue.py pending --count`), say how many and that "sync my CRM" applies them. Then positive replies first, by name and company, then questions, referrals and the counts for everything else. More than a few bounces in a day means the lead filters or the sending domain need a look. Say so.

Based on the public playbook design.
