# Install

About an hour, start to finish, and you never touch a terminal. Claude does the installing; you read what it tells you and click Allow. Based on the public playbook design.

## What you need

- **A paid Claude plan, and the Claude desktop app** (claude.com/download). The kit runs in its Code tab.
- **An Apollo account with credits.** Use them to get your leads' emails and paste those in, or get the emails any other way. On a paid Apollo plan, Claude can pull them directly.
- **A CRM:** HubSpot (the free plan works), Salesforce or Attio. No CRM is fine too: the kit keeps its own log.
- **Gmail or Outlook**, the account you'll send from.

## 1. Ask Claude to install it

1. Download the kit. Leave it in your Downloads folder.
2. Open the Claude desktop app and click the **Code** tab. Start a new session, and when it asks for a folder, pick **Downloads**.
3. Paste this and press Enter:

> Install the outbound kit from my Downloads folder: find the claude-outbound-kit download, unzip it if needed, then read SETUP.md inside it and follow it.

Claude finds the kit, makes sure Python works (on a new Mac, Apple shows a box to install developer tools: click Install), copies the skills into place, checks them, and goes straight into setup. Before every box that asks your permission, Claude tells you in plain words what you're allowing. When it says to pick **Always allow**, do: later runs happen on a schedule with nobody there to click.

Along the way it walks you through connecting your email, your CRM and, on a paid plan, Apollo (Customize → Connectors). Those are sign-in screens, so they're the one part you click through yourself.

## 2. Setup

Claude starts this right after installing. If it doesn't, or you stop halfway and come back later, open the Code tab and say:

> Set up the outbound agent

It checks your connectors, reads your website, interviews you (it proposes answers, you confirm or fix them), builds your voice bank from 20 or more of your sent emails, and asks who could introduce you to buyers. Then it runs a test batch of 10 leads by hand, so you can approve some, kill one and edit one before anything runs on a schedule.

**During that first hand run, choose "always allow"** each time Claude asks permission to use a tool (Apollo search, sending email, CRM writes, running the scripts). Scheduled runs can't stop to ask. CRM writes are the exception: they ask every time, so scheduled runs queue them and you apply them by saying "sync my CRM" in Claude.

## 3. Turn on the schedule

At the end of onboarding, say yes to turning on the schedule. It creates five scheduled tasks:

| Task | Prompt | When |
|---|---|---|
| Daily batch | Run the outbound-daily-batch skill. This is a scheduled run. | Weekdays 6:00 |
| Follow-ups | Run the outbound-followups skill. This is a scheduled run. | Weekdays 7:00 |
| Approval sweep | Run the outbound-approval-sweep skill. This is a scheduled run. | Every 30 minutes, 8:00 to 18:00, weekdays |
| Reply triage | Run the outbound-reply-triage skill. This is a scheduled run. | 12:00 and 16:00, weekdays |
| Weekly report | Run the outbound-weekly-report skill. This is a scheduled run. | Fridays 15:00 |

Start at 20 new leads a day. Go up toward 50 as your edits get lighter (the Friday report tells you when). Each new lead becomes about 3 emails over 8 days, so `volume.max_sends_per_day` (30 to start) is the real ceiling: when it's reached, new leads are held back and approved emails go out the next day.

## Your daily routine (about 20 minutes)

1. Open today's review file: `~/.claude/skills/outbound-core/state/queue/<today's date>.md`. Anything you didn't get to in an earlier file still sends once you approve it there.
2. Warnings (a failed run, a blocked send) and priority items (positive replies, intro asks) are at the top. Handle those first.
3. For each draft, set `status:` to ✅ to send or ❌ to kill. Edit the subject or message between the message markers first if you want: the kit learns from edits you keep making.
4. Tasks ask you to do something only you can: ask a friend for an intro, or check whether someone replied on LinkedIn. Set ✅ or ❌.
5. Send any approved LinkedIn messages by hand, then set their status to `sent`.
6. Save the file. The next sweep sends what you approved.

## Scheduling notes

- **Local scheduled tasks need your computer awake** and the Claude desktop app running at those times.
- **Grant "always allow" on the first hand run.** A scheduled run that hits a tool it doesn't have permission for stalls until someone approves it.
- **A tool that asks every single time will stall every scheduled run.** If sending email asks for approval on every message with no always-allow option, set `"email_send_mode": "draft"` in `~/.claude/skills/outbound-core/config.json`. Approved emails then land in your drafts folder and you click send.
- **No desktop app?** A cron job can run the same prompts with `claude -p "<prompt>"`. Headless runs can't ask for permission, so pass an `--allowedTools` list that covers Bash and your connectors (see Claude Code's headless docs).
- **Cloud routines aren't supported yet.** They start each run from a fresh copy of a repository, so the send log wouldn't carry over between runs and approved emails could go out again. Use local scheduled tasks.

## Sending more than about 30 emails a day

Above about 30 a day (all touches together), send from a separate domain (for example `getacme.com` instead of `acme.com`) so your main inbox's reputation stays safe. Set up SPF, DKIM and DMARC on it, and warm it for 2 to 3 weeks before sending outreach. Start this early, since warming takes time. Once it's warm, raise `volume.max_sends_per_day` in `config.json`.

## Updating the kit

Download the new version into Downloads, open the Code tab, and paste the same sentence as step 1. Claude sees the kit is already installed and updates it without touching your company files, voice bank, settings, banned phrases or log.

By hand, from the unzipped kit folder:

```bash
cp -R skills/outbound-onboarding skills/outbound-daily-batch skills/outbound-approval-sweep skills/outbound-followups skills/outbound-reply-triage skills/outbound-weekly-report ~/.claude/skills/
```

```bash
rsync -a --exclude config.json --exclude company/ --exclude person/ --exclude state/ --exclude engine/banned.txt skills/outbound-core/ ~/.claude/skills/outbound-core/
```

Then run the check again. If it reports missing settings, copy those keys from the new `config.json` into yours, and look at the new `engine/banned.txt` for phrases worth adding to yours.

## Troubleshooting

| Problem | Fix |
|---|---|
| `check.py` says a skill folder is missing | Paste the install sentence from step 1 again |
| Python is missing or too old | Ask Claude: "Make sure Python works for the outbound kit." On a Mac, click Install when Apple's box appears |
| Claude doesn't pick up the skills | Start a new session in the Code tab, then say "Set up the outbound agent" |
| Apollo credits are running out fast | Lower `volume.new_leads_per_day` in `config.json`, or tighten the filters in `company/icp.md` |
| Lots of drafts fail lint on numbers | The number isn't in `company/claims.md`. Add claims you're comfortable using, word for word |
| Drafts don't sound like you | Add more of your real sent emails (rerun the voice bank step in onboarding), and keep editing drafts: the kit learns from edits |
| A scheduled run didn't happen | Your computer was asleep or the desktop app was closed. Run it by hand: say the task's prompt |
| A scheduled run stalled | It hit a permission box. Run it by hand once and choose "Always allow". If sending email asks every time, ask Claude to switch the kit to draft mode |
| Emails land in spam | New inboxes need time. Keep volume low, avoid links in first touches, set up SPF/DKIM/DMARC, and move to a separate warmed domain above about 30 a day |
| A send says "daily send cap reached" | Working as intended: it goes out tomorrow. Raise `volume.max_sends_per_day` only once you send from a warmed separate domain |
| An approved item says `blocked:` | The thread changed after the draft was made (they replied, booked, unsubscribed or bounced), or your edit broke a rule. Read the reason; fix and re-approve if it still makes sense |
| The review file has a note about an unrecognized status | Use ✅, ❌, or `sent` (for LinkedIn). Words like "approve", "yes", "kill" and "no" work too |
| The check notes unconfirmed sends | A run stopped mid-send. The next sweep checks your Sent folder and finishes or retries each one |
| My edits in the review file disappeared | Save before the next sweep or triage run. The scripts only add new items and change status lines, but an editor holding an unsaved copy can overwrite the file |
| Too many learned rules | The weekly report merges and retires them. You can also edit `person/learned-rules.md` by hand. The cap is `learning.max_learned_rules` |

## Installing by hand (for terminal users)

Skip this if Claude installed it for you. Needs Python 3.9 or newer (`python3 --version`).

### Copy the skills

Unzip the kit, open a terminal in the unzipped folder, and run:

```bash
mkdir -p ~/.claude/skills && cp -R skills/outbound-* ~/.claude/skills/
```

### Run the check

```bash
python3 ~/.claude/skills/outbound-core/scripts/check.py
```

Every line should say `ok`. Lines that say `note` are fine for now: onboarding takes care of them. If a line says `FAIL`, it tells you the fix.

### Connect your tools

In Claude, open **Customize → Connectors** and connect:
- Gmail or Outlook
- your CRM (HubSpot, Salesforce or Attio)
- Apollo, if you're on a paid plan

Then say "Set up the outbound agent" in Claude Code.
