---
name: outbound-daily-batch
description: Drafts today's new outbound messages. Pulls leads matching the ICP and signals through the Apollo connector, or takes leads the user pastes in, runs hold checks before any paid lookup, skips anyone without a verified email, researches each with sources, runs the drafting pipeline, lints, checks the batch for sameness, and queues drafts for review. Use when the user says "run the outbound daily batch", "draft today's outreach", "run the daily batch", or a scheduled task asks for it.
model: sonnet
---

# Outbound daily batch

`$CORE` is the `outbound-core` folder next to this skill's folder (usually `~/.claude/skills/outbound-core/`). Read `$CORE/config.json`, `$CORE/engine/pipeline.md` and `$CORE/engine/tiers.md` before starting. If anything breaks, follow "If something breaks" in `$CORE/SKILL.md`.

If the prompt says this is a scheduled run, don't stop to ask questions. Skip anything that needs the user and say so in the summary.

## 1. Before anything
- If `$CORE/company/icp.md` still has `[placeholders]`, onboarding isn't finished: stop and say so.
- `python3 "$CORE/scripts/log.py" budget` gives `new_leads_today`: the configured number, cut down so today's sends stay under `volume.max_sends_per_day` after the follow-ups that are due. If the user asked for a specific number (such as 10 during onboarding), use that instead.
- `python3 "$CORE/scripts/review_queue.py" summary` gives `email_first_touches_queued` for today. If the batch already ran today, draft only the difference. If that's zero, stop.

## 2. Pull candidates
With `lead_source` `apollo` (or not set), use the Apollo connector's people search with the filters in `$CORE/company/icp.md` → "Lead search". Ask for about twice the target, since many will be held or skipped.

With `lead_source` `paste`, use the leads the user gave you: name, email and company at least, in any format. If they haven't given any, ask for them. In a scheduled run, stop and say so in the summary.

## 3. Hold checks (before any email lookup)
Email lookups cost credits, so check first. For each candidate:
- `python3 "$CORE/scripts/log.py" seen <company domain>`. If `hold` is true, skip (someone there is mid-sequence, recently contacted, queued, or never-contact).
- Check the CRM following `$CORE/company/crm.md` → "Hold checks": open deals, current customers, anyone a rep contacted in the window.
- Check `icp.md` → "Seniority ceiling" and "Disqualifiers".

## 4. Verified email only
Look up the email through Apollo. **Skip anyone whose email status isn't verified.** Pasted leads skip the lookup: use the email they gave you, and remind them once to paste only emails they trust, because bounces hurt their inbox. Then `log.py seen <email>` and skip if `hold` is true. Log every skip and hold with a reason:

```bash
echo '{"event": "skipped", "lead_id": "...", "email": "...", "reason": "no-verified-email"}' | python3 "$CORE/scripts/log.py" add
```

Pipe JSON on stdin like this throughout, so apostrophes in names can't break the command.

## 5. First-guess tier
From the lead record, the CRM and `$CORE/person/warm-paths.md`, guess A, B or C (`tiers.md`). Work through leads in tier order, A first.

## 6. Research, select, draft
Run the pipeline in `$CORE/engine/pipeline.md` (`pipeline_mode` full or lean). Batch two or three leads per subagent call per stage.

**In full mode, never write the message yourself.** The selector, writer, cutter and judge each run as their own subagent call (the Agent tool), even for a single lead. The review queue refuses a full-mode email draft that has no judge result. If you can't start subagents, stop, log the run as `failed`, and say why. For the selector, include today's angles so far, so the batch spreads across angles.

- **Writer examples:** `python3 "$CORE/scripts/voice.py" pick --channel <channel> --touch 1 --angle <angle> --segment <segment> --seed <lead id> --query "<words from the brief's fact and guess>" --n <learning.examples_per_draft>`
- **Judge example:** `voice.py pick --channel <channel> --replied --n 1 --seed <lead id>`
- **Lint:** pipe the draft with its brief to `python3 "$CORE/scripts/lint.py"`.

What the selector decides:
- **`route: hold`**: log a skip with `"reason": "hold: <reason>"`.
- **`route: intro_first`**: queue a task for the human, with a short draft asking `intro_via` for the introduction, written in the sender's voice:
  ```json
  {"lead": {...}, "task_type": "intro", "via": "Raj Patel", "priority": true,
   "task": "Ask Raj Patel for an intro to Dana Reyes (Reyes Plumbing): <one-line reason>", "body": "<draft ask>"}
  ```
  piped to `python3 "$CORE/scripts/review_queue.py" task`.
- **`route: direct`**: draft as usual.

**LinkedIn** (only if `channels.linkedin` is true): for tier A and B leads with a LinkedIn URL, also draft a LinkedIn touch 1. If they're not connected and `channels.linkedin_cold_starts_with` is `connection_note`, the channel is `linkedin_connect` (300 characters). Otherwise it's `linkedin`. It's sent by hand.

## 7. Queue
Pipe each passing draft to `python3 "$CORE/scripts/review_queue.py" add`:

```json
{"lead": {"id": "...", "name": "...", "email": "...", "company": "...", "title": "...", "linkedin": "..."},
 "channel": "email", "touch": 1, "kind": "new", "tier": "B", "segment": "...", "angle": "...",
 "subject": "...", "body": "...", "brief": {...}, "sources": ["https://..."], "judge": {...}}
```

It re-lints, refuses hard fails, refuses anyone already waiting in a queue (and anyone at a company that already has someone waiting), and decides auto-approval for segments at autonomy level 3 or higher.

## 8. Batch sameness
`python3 "$CORE/scripts/lint.py" --batch <today>`. For each id in `flagged_ids`, rewrite the draft with the writer (tell it which opener or phrase to avoid). Then cutter and lint, and swap it in with `review_queue.py replace <id>`, piping `{"body": "...", "subject": "..."}`.

## 9. Finish
- `python3 "$CORE/scripts/log.py" run daily-batch ok "queued N, held M"`. Use `partial` or `failed` if something broke, with the reason.
- If a connector failed or the batch stopped early, also run `review_queue.py note "<what failed and what to do>"` so the human sees it at the top of the review file.
- **Summary:** queued (by tier), intro asks, held and skipped (by reason), roughly how many Apollo lookups were used, and the path to today's review file. If lookups look high for the result, suggest tightening the ICP filters.

Based on the public playbook design.
