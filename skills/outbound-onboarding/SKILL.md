---
name: outbound-onboarding
description: One-time setup for the outbound sales kit. Checks connectors, reads the user's website, interviews them to fill in the company files, builds a voice bank from their sent mail and LinkedIn messages, sets the approval surface and limits, runs a 10-lead test batch, and turns on the schedule. Use when the user says "set up the outbound agent", "set up outbound", "onboard me to the outbound kit", or wants to redo their company files or voice bank.
model: sonnet
---

# Outbound onboarding

Takes about an hour with the user. `$CORE` is the `outbound-core` folder next to this skill's folder (usually `~/.claude/skills/outbound-core/`). Read `$CORE/SKILL.md` first.

**Writing kit files:** Claude Code protects `~/.claude/` from direct file writes, so every company file, person file and config change goes through the kit's script: pipe the full new file text to `python3 "$CORE/scripts/kit_write.py" <path>`, for example `company/offer.md` or `config.json`. Read the current file first and send the whole updated file.

Many users have never used a terminal. Before any action that will ask their permission, say in one plain sentence what it does and why, and give the action a plain-words description (the permission box shows it). Never ask them to type a command or find a folder: do it yourself.

Work through the steps in order, and tell the user which step you're on. Propose answers for them to confirm instead of asking open questions: they should mostly be saying "yes", "no" or "change X".

## 1. Check the install
Run `python3 "$CORE/scripts/check.py"`. Fix any FAIL before going on. Notes about unfilled files are expected at this point.

## 2. Check the connectors
Connectors are added in Claude under **Customize → Connectors** (in the terminal, `/mcp` shows what's connected). Test each one with a harmless read. For any that's missing, walk them through it one at a time in plain clicks ("Click Customize at the bottom left, then Connectors, then Connect next to Apollo, and sign in"), wait for them to say it's done, and test it again before moving on:
- **Lead source:** ask how they'll get leads, and set `lead_source`:
  - **Pull them directly (`apollo`):** needs a paid Apollo plan with the connector on. Test it with a small people search (one title, one location, 3 results).
  - **Paste them in (`paste`):** they get the emails with their Apollo credits, or any other way, and paste them to you when they run the batch. No connector needed. If the search test fails on Apollo's free plan, explain this option and carry on with it.
- **Email (Gmail or Outlook):** search the sent folder for one message. Set `email_provider`.
- **CRM (HubSpot, Salesforce or Attio):** look up any one contact. With no CRM, set `crm` to `none` and the kit's own log is the record.

Report what's connected and what's missing. Don't continue without email.

## 3. Read their website
Ask for the company website. Read the home page, the product or services page, pricing if public, and any case studies. Take notes for step 4.

## 4. Interview and write the company files
For each file in `$CORE/company/`, draft it from the website and what you know, show the draft, and have them confirm or correct it. Replace every `[placeholder]`. In order:

1. **`offer.md`:** what they sell, the outcome, and proof. For each piece of proof, ask who it looks like. Also value assets for touch 2, and the booking link.
2. **`icp.md`:** who buys and who doesn't, plus the exact lead-search filters. Ask directly:
   - "Is anyone off-limits for a cold first email, like executives at big companies, or anyone above a certain title? 'Nobody' is a fine answer." That's the seniority ceiling.
   - "Any competitors, partners or customers to exclude?" Those are the disqualifiers.
3. **`personas.md`:** one section per segment, with short stable names. For each, ask:
   - what they're measured on
   - what makes them reply and what makes them delete
   - one question they'd happily answer in a line
4. **`signals.md`:** offer a ranked menu of likely signals for their market. Each gets a freshness window.
5. **`angles.md`:** 3 to 6 angles, with short stable names, each with the guess it leads to.
6. **`claims.md`:** every number they're comfortable using, word for word; clients they can and can't name; and anything never to say. The lint script blocks any stat-like number not listed here, so be thorough. Keep the headings exactly as they are.
7. **`crm.md`:** rewrite it for their CRM's field names, plus their never-contact list (one email or domain per bullet). Keep the task type on every task. If positive replies get a deal, look up their deal pipeline and the stage to use now, and write both names in, so a scheduled run never has to look them up.

## 5. Build the voice bank
1. From the email connector, collect 20 or more emails the user wrote themselves to one person: outreach, follow-ups, short business notes. Skip newsletters, invoices, calendar replies, one-liners and anything mostly quoted. Prefer recent ones, and for each, check whether the other person replied in the thread.
2. Save them to a temporary file, one JSON per line: `{"subject": "...", "body": "...", "to": "...", "date": "...", "got_reply": true}`.
3. Run `python3 "$CORE/scripts/voice.py" build <that file>`. If it warns there are too few, ask the user to paste 10 to 20 messages they wrote. Add those to the file and run it again.
4. If they use LinkedIn, ask for their data export: Settings → Data privacy → Get a copy of your data → Messages. Run `voice.py import-linkedin messages.csv --me "<their name exactly as LinkedIn shows it>"`.
5. From the printed profile and the kept messages, fill in `$CORE/person/voice-bank.md`. Show it to the user and confirm.
6. Set `sender.greeting` and `sender.signoff` in config.json to match.
7. Delete the temporary file.

## 6. Warm paths
Ask: "Who could introduce you to buyers like these? Which groups or communities actually know you? Any past customers or conversations?" Write the answers to `$CORE/person/warm-paths.md`. Leads with a real route through these get an intro ask instead of a cold note.

## 7. Settings
Propose these and write the confirmed values to `$CORE/config.json`:
- **Sender:** `sender.name`, `sender.email`, `sender.company`.
- **LinkedIn:** `channels.linkedin` on only if they'll send LinkedIn messages by hand.
- **Sending:** `email_send_mode` is `send` (default) or `draft`. Also set `booking_link`.
- **Pipeline:** `pipeline_mode` is `full` (default). Offer `lean` only if they're on a smaller Claude plan and worried about usage. Lean drafts never auto-send.
- **Volume:** `volume.new_leads_per_day` starts at 20, and `volume.max_sends_per_day` at 30. Explain the math: each new lead becomes about 3 sends over 8 days, so 20 new a day means roughly 50 to 60 sends a day once follow-ups start, and the daily cap holds new leads back to make room. Above about 30 a day, they should send from a separate domain with SPF, DKIM and DMARC, warmed for 2 to 3 weeks. Raise `max_sends_per_day` once that's in place.
- **Autonomy:** leave `autonomy.default_level` at 2.

Run `check.py` again. It should pass with no notes about unfilled files.

## 8. Test batch of 10
Run the `outbound-daily-batch` skill with 10 leads (with `lead_source` `paste`, ask them to paste 10 first). Then open the review file with the user (`$CORE/state/queue/<today>.md`) and walk through it: approve some (✅), kill one (❌), edit one in place between the message markers. Then run `outbound-approval-sweep` by hand.

The first time each tool asks for permission (Apollo search, email send, CRM write, file writes, running Python), tell the user before the box appears to choose **always allow**, and why. Scheduled runs can't stop to ask. If sending email asks every single time with no always-allow option, set `email_send_mode` to `draft`. CRM writes can ask every time too, so scheduled runs never write to the CRM: they queue updates, and the user says "sync my CRM" once a day or so to apply them. Tell the user that.

## 9. Turn on the schedule
Ask whether to set up the schedule now. If yes, create these as Claude Code scheduled tasks. With `lead_source` `paste`, leave out the daily batch, since it needs them there to paste leads: they say "run the daily batch" when they have some. For any task the user leaves out, set its entry in `config.json` → `schedule` to `"off"` (through `kit_write.py`), so the weekly report doesn't count it as missed. Local tasks need the computer awake and the desktop app open. Each prompt names the skill and says it's scheduled, so the skill knows not to stop and ask:

| Task | Prompt | When |
|---|---|---|
| Daily batch | Run the outbound-daily-batch skill. This is a scheduled run. | Weekdays 6:00 |
| Follow-ups | Run the outbound-followups skill. This is a scheduled run. | Weekdays 7:00 |
| Approval sweep | Run the outbound-approval-sweep skill. This is a scheduled run. | Every 30 minutes, 8:00 to 18:00, weekdays |
| Reply triage | Run the outbound-reply-triage skill. This is a scheduled run. | 12:00 and 16:00, weekdays |
| Weekly report | Run the outbound-weekly-report skill. This is a scheduled run. | Fridays 15:00 |

Tell them the daily routine: about 20 minutes in the review file. Notes and priority items are at the top, so answer positive replies first.

Based on the public playbook design.
