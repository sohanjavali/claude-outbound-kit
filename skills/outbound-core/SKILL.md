---
name: outbound-core
description: Shared rules, pipeline prompts, company and voice files, state and scripts for the outbound sales kit. The other outbound-* skills read it. Use directly when the user asks about the outbound kit's settings, rules, files or how it works, or wants to change a setting in config.json. Also use when the user says "sync my CRM", "apply the CRM updates" or "push the pending CRM changes", or wants to review drafts: "show me today's outbound drafts", "what's in my review queue", "approve 1 and 3". Also use when something seems broken: "fix my outbound kit", "my outbound stopped working", "something's wrong with outbound".
model: sonnet
---

# Outbound kit: shared core

The six working skills share this folder: `outbound-onboarding`, `outbound-daily-batch`, `outbound-approval-sweep`, `outbound-followups`, `outbound-reply-triage` and `outbound-weekly-report`. It doesn't do work on its own.

Every skill calls this folder `$CORE`. It's the `outbound-core` folder next to the skill's own folder, usually `~/.claude/skills/outbound-core/`. Scripts run as `python3 "$CORE/scripts/<name>.py"`, and `--help` lists each script's commands. Pipe JSON to scripts on stdin rather than quoting it on the command line, so apostrophes in names can't break anything.

## What's here

| Path | What it is | Who writes it |
|---|---|---|
| `config.json` | Every setting, in one place | Onboarding, then the user |
| `engine/message-standard.md` | Twelve principles every message follows | The kit |
| `engine/sequence.md` | 3 touches on days 0, 4, 8, the arc, length budgets, the offer ladder | The kit |
| `engine/tiers.md` | Hold checks, warm paths first, then tiers A, B and C | The kit |
| `engine/autonomy.md` | The autonomy ladder, per segment | The kit |
| `engine/banned.txt` | Banned phrases (add your own at the bottom) | The kit, then the user |
| `engine/pipeline.md` | How one lead becomes one draft, full and lean modes | The kit |
| `engine/research.md`, `brief-format.md`, `selector.md`, `writer.md`, `cutter.md`, `judge.md`, `lean.md` | The prompt for each pipeline stage | The kit |
| `company/` | ICP, signals, offer and proof, allowed claims, personas, angles, CRM conventions | Onboarding |
| `person/voice-bank.md` | The sender's voice profile | Onboarding |
| `person/examples.jsonl`, `sent-corpus.jsonl` | Real messages the writer matches | `voice.py`, `learn.py` |
| `person/warm-paths.md` | People and groups that make a lead warm | Onboarding |
| `person/learned-rules.md` | Short rules learned from repeated edits | `learn.py`, via the weekly report |
| `state/outreach-log.jsonl` | Append-only log of every send, kill, reply, stop and skip | `log.py` |
| `state/runs.jsonl` | One line per skill run, ok or failed | `log.py run` |
| `state/crm-pending.jsonl` | CRM updates scheduled runs couldn't apply, waiting for "sync my CRM" | `crm_queue.py` |
| `state/queue/DATE.md` | The review file the human edits | `review_queue.py`, then the human |
| `state/reports/` | Weekly reports | Weekly report |
| `scripts/` | `lint.py`, `log.py`, `review_queue.py`, `voice.py`, `learn.py`, `edit_rate.py`, `crm_queue.py`, `kit_write.py`, `check.py` | The kit |

## Settings (`config.json`)

| Setting | Default | What it does |
|---|---|---|
| `sender.name`, `email`, `company` | empty | Who the messages come from |
| `sender.greeting`, `sender.signoff` | `Hi {first_name},`, empty | How the sender opens and signs off |
| `volume.new_leads_per_day` | 20 | New first touches drafted each weekday, if the send cap leaves room |
| `volume.max_new_leads_per_day` | 50 | The ceiling for raising volume |
| `volume.max_sends_per_day` | 30 | Emails sent per day, all touches together. The sweep stops here and continues tomorrow |
| `volume.skip_if_contacted_within_days` | 90 | Anyone contacted within this window is held |
| `channels.email`, `channels.linkedin` | true, false | Channels to draft for. LinkedIn is always sent by hand |
| `channels.linkedin_cold_starts_with` | connection_note | A cold LinkedIn touch 1 is a connection note (300 characters) |
| `email_provider` | gmail | `gmail` or `outlook` |
| `email_send_mode` | send | `send`, or `draft` to put approved email in the drafts folder |
| `lead_source` | apollo | `apollo` pulls leads through the connector (needs a paid Apollo plan). `paste` uses leads the user pastes in, however they got them |
| `crm` | hubspot | `hubspot`, `salesforce`, `attio` or `none` |
| `booking_link` | empty | Sent when someone says yes |
| `pipeline_mode` | full | `full` (separate calls, with a judge) or `lean` (budget mode, never auto-sends) |
| `autonomy.default_level` | 2 | 1 to 4 (`engine/autonomy.md`) |
| `autonomy.segments` | {} | Segments that earned a higher level, for example `{"owners": 3}` |
| `autonomy.spot_check_rate` | 0.1 | Share of auto-approved drafts held for the human |
| `autonomy.promote_after`, `demote_if_spot_edit_rate_above` | 80% untouched for 3 weeks with 30+ sends; 30% | When the weekly report recommends moving a segment |
| `sequence.max_touches` | 3 | Up to 5 |
| `sequence.spacing_days` | [0, 4, 8] | Day of each touch, counted from touch 1. Later touches come every 4 days |
| `limits` | see `sequence.md` | Word caps per channel and touch, connection-note characters, subject length, reading grade, batch sameness |
| `queue.max_age_days` | 14 | Older review files are ignored |
| `research.max_sources_per_lead`, `signal_max_age_days` | 5, 90 | Research limits |
| `learning.examples_per_draft` | 5 | Voice examples given to the writer |
| `learning.max_examples` | 200 | Example bank size. The sender's own mail is kept longest |
| `learning.max_learned_rules`, `rule_evidence` | 15, 3 | Rule cap, and how many matching edits a new rule needs |
| `schedule` | weekdays | When each skill runs (used when setting up scheduled tasks). `"off"` means that skill has no scheduled task |
| `deliverability.separate_domain_above_per_day` | 30 | Above this, send from a separate warmed domain |

## Rules for every skill

- **Explain before every permission box:** when someone is watching, say in one plain sentence what the next action does and why before you take any action that will ask their permission, and give the action a plain-words description, since that's what the box shows. Many users have never used a terminal. In a scheduled run, just work.
- **Approval:** nothing sends without approval unless `engine/autonomy.md` allows it. Auto-approval is decided once, when a draft is queued.
- **Before every email send:** run `log.py claim <id>`, and log the send right after. That's what stops a message going out twice or over the daily cap.
- **LinkedIn is never automated.** LinkedIn messages are drafted for the human to send by hand.
- **Sources:** every fact in a message has a source URL. Nothing unverified goes in a message.
- **Logs are append-only.** Never edit or delete lines in `state/outreach-log.jsonl` or `state/runs.jsonl`. Review files change only through the human and `review_queue.py`.
- **Scheduled runs:** in a scheduled run (the prompt says so), don't stop to ask questions. Skip what needs the human and say so in the summary.
- **Writing kit files:** never write into this folder with the file-writing tool (Claude Code protects `~/.claude/`). Pipe the text to `scripts/kit_write.py <path>`. Scripts handle the logs and queues themselves.
- **CRM writes:** CRM connectors ask for approval on each write, and a scheduled run can't answer. So in a scheduled run, never call a CRM write tool. Pipe each update to `scripts/crm_queue.py add` instead, with `action`, `email`, `ref` (the queue id or message_id) and `do` (what to change, in plain words, following `company/crm.md`), plus the fields the CRM needs (name, company, title, subject, body, next task date). In a run the human is watching, write to the CRM directly. Reading the CRM (hold checks) is fine either way. With `crm` set to `none`, do neither.
- **Run log:** every skill ends with `log.py run <skill> ok|partial|failed`. When something fails, it also leaves a `review_queue.py note`, so the human sees it at the top of the review file.

## If something breaks
When a step fails, or the user says something's wrong ("fix my outbound kit"), try to fix it before reporting it. Don't give up on the first error.
1. Run `scripts/check.py` and read the actual error. Fix the cause, then retry the step once.
2. **Fine to fix:** a typo that makes `config.json` invalid, keeping every value as it was (write it with `kit_write.py`). A missing kit file, restored from the `claude-outbound-kit` download in Downloads, never touching `config.json`, `company/`, `person/`, `state/` or `engine/banned.txt`. A connector hiccup, retried after a minute. Bad input you passed to a script. A run the Mac slept through: this run does its work as normal.
3. **Never "fix" something by:** resending a message that might have gone out (follow the `log.py unconfirmed` steps in the approval sweep), changing approval, autonomy, caps or any other setting, skipping the lint or the judge, editing the logs, or rewriting the kit's scripts or rules. If one of those is the only way through, it counts as can't fix.
4. **Can't fix it?** Stop that step, carry on with whatever doesn't depend on it, log the run as `partial` or `failed`, and leave a `review_queue.py note` (if that fails too, put it in the run log and your final message). Write it for someone who has never used a terminal: what's wrong, what's affected, and the exact clicks to fix it, such as "Click Customize, then Connectors, then Connect next to Gmail, and sign in." If it needs the kit's maker, tell them to email the support address on their Start Here page with the error. If someone is watching, tell them directly too.

## Review drafts with the user
When the user asks to see or decide on drafts (they may never open the review file themselves):
1. Read today's review file, `state/queue/<today>.md`, plus `review_queue.py summary` for older open items. Show warnings and priority items first, then each pending draft with its number, who it's to, the subject and the full message.
2. Record each decision they give ("approve 1 and 3, kill 2") with `review_queue.py set <id> ✅` or `❌`. Confirm back what you set.
3. **Edits:** the file is theirs to edit, and Claude Code protects `~/.claude/` from your file-writing tool. If they want to change wording, open the file for them in their text editor (`open -t <path>` on a Mac, explained first), tell them to edit between that draft's message markers and save, then run `review_queue.py parse` to re-check it before setting ✅.
4. Tell them approved emails go out at the next sweep, within 30 minutes (or land in Drafts in draft mode).

## Sync the CRM
When the user says "sync my CRM" (never in a scheduled run):
1. `python3 "$CORE/scripts/crm_queue.py" pending` lists waiting updates, oldest first. If there are none, say so and stop.
2. Tell the user how many there are and that the CRM will ask to approve each write.
3. For each update, in order, do what its `do` says in the CRM, following `company/crm.md`. Look the contact up by email first: update it if it exists, create it if not, so nothing is duplicated.
4. After each one goes through, `crm_queue.py done <id>`. If the user declines one or it no longer makes sense (say the contact was deleted on purpose), `crm_queue.py skip <id> "<reason>"`. If a write fails, leave it pending for next time.
5. Summary: applied, skipped, and still pending.

Based on the public playbook design.
