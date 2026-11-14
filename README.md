# Claude Outbound Kit

An outbound sales system that runs on your own Claude subscription. Every weekday it finds people who match your ideal customer, researches each one with sources, writes a short message in your voice, checks it, and puts it in a review file. You approve, kill or edit each draft in about 20 minutes. It sends what you approve from your own email, logs it to your CRM, follows up, sorts replies, and learns from your edits.

There's no app and no server. It's a set of Claude Code skills: folders of instructions and small Python scripts that tell Claude what to do and in what order.

Based on the public playbook design.

## What's inside

| Skill | What it does | When it runs |
|---|---|---|
| `outbound-onboarding` | Interviews you, reads your website, writes your company files, builds a voice bank from your sent mail, runs a test batch, turns on the schedule | Once |
| `outbound-daily-batch` | Finds leads, researches them, drafts one message each, checks it, queues it for review | Weekdays 6:00 |
| `outbound-followups` | Drafts the next touch for threads that are due, after checking for replies and news | Weekdays 7:00 |
| `outbound-approval-sweep` | Sends what you approved, logs it to the CRM, learns from your edits | Every 30 minutes, 8:00 to 18:00, weekdays |
| `outbound-reply-triage` | Sorts replies, stops sequences, drafts answers, queues your booking link on a yes | 12:00 and 16:00, weekdays |
| `outbound-weekly-report` | Replies, meetings and edit rate by angle, segment and warmth, plus when to hand over more | Fridays 15:00 |
| `outbound-core` | The shared rules, prompts, your company files, your voice bank, the log and the scripts | Read by the others |

## How one message gets written

1. Find leads that match your ideal customer and buying signals, with verified emails only.
2. Hold anyone it shouldn't write to (an open deal, someone a colleague is already talking to, too senior for a cold note). Where you have a mutual connection, it suggests asking for an intro instead.
3. Sort the rest by warmth: warm (you've talked before), active (a buying signal), cold (a fit, nothing more).
4. Research each one. Every fact gets a source link. Anything unverified stays out.
5. A selector picks one fact that matters to them, a guess about their problem they can correct, and one easy question.
6. A writer drafts from that brief and 3 to 5 of your real past messages, favouring the ones that got replies.
7. A cutter, whose only job is deleting, makes it shorter.
8. A script checks the hard rules (length, one question, banned phrases, unapproved numbers, leftover placeholders). A separate judge compares it blind against a real message of yours that got a reply, scores it, and fact-checks it. The whole batch is checked so no two messages sound the same.
9. You approve it.
10. It sends from your email, never twice and never over your daily cap. LinkedIn messages are drafted for you to send by hand.
11. It logs the message and sets the next follow-up in your CRM. Scheduled runs queue CRM changes, since the CRM asks before each write, and you apply them by saying "sync my CRM".
12. Your sent messages become examples, and edits you keep making become rules, so drafts sound more like you every week.
13. Every Friday you get a report.

## The rules every message follows

First emails are 50 to 80 words (90 at most, a little more only when carrying a sourced number or link), follow-ups shorter still, LinkedIn notes 25 to 40. Their world in the first 12 words. One concrete fact stated plainly, no compliments. A guess about their problem they can correct, then exactly one easy question about their world, never a meeting ask on the first touch. Plain text at about a grade 6 reading level. Sequences run 3 touches on days 0, 4 and 8 (up to 5 if you want): the first earns a conversation, the second gives something useful, the third brings in the offer. The full standard is in `skills/outbound-core/engine/message-standard.md`.

## You stay in control

The kit starts at level 2 of 4 on the autonomy ladder: it drafts, and you approve every message. It only suggests handing over more, one segment at a time, when the numbers say your drafts go out untouched, and it tells you when a segment should drop back. Some things never send on their own at any level: LinkedIn, cold notes to senior people, and anything the judge didn't pass. See `skills/outbound-core/engine/autonomy.md`.

## Start here

Download the kit, open the Code tab in the Claude desktop app, and paste:

> Install the outbound kit from my Downloads folder: find the claude-outbound-kit download, unzip it if needed, then read SETUP.md inside it and follow it.

Claude installs it and walks you through setup, explaining every permission before you click Allow. No terminal. Details in [INSTALL.md](INSTALL.md). Setup takes about an hour, then about 20 minutes a day.
