# Autonomy ladder

Autonomy is earned one segment at a time, measured by how often the human sends drafts untouched. Every segment starts at level 2. Levels live in `config.json`: `autonomy.default_level` for everything, and `autonomy.segments` for segments that earned more, for example `{"owners": 3}`.

| Level | Name | What happens | Move up when | Move down when |
|---|---|---|---|---|
| 1 | Research assistant | The kit finds leads and writes briefs. Every message is written by the human | The briefs keep holding up when the human checks the sources | |
| 2 | Approval queue (**default**) | The kit drafts. The human approves, edits or kills every message | About 80% of the segment's drafts go out untouched for three weeks in a row, with 30+ sends | The human's call, if briefs keep needing rework |
| 3 | Audit mode | New messages and follow-ups in this segment that pass lint and the judge go out without review. About one in ten is held back for the human to check | Reliable at 3 for a long stretch, and the human wants it | Spot-check edits above 30% in a week, or any complaint |
| 4 | Autonomous | Everything level 3 does, plus replies that only share the booking link after a clear yes | | Any wrong fact or any complaint |

## How auto-approval works

Auto-approval is decided **once, when a draft is queued**, and saved on the item (`auto: true`, or `spot_check: true` for the one in ten held back). The approval sweep only reads that decision, so a held draft stays held. The human sees auto-approved items in the review file and can still kill them before the next sweep.

## Never above level 2, at any setting

- Any LinkedIn message. LinkedIn is always sent by hand.
- A cold first touch to someone senior (VP, C-level, founder or owner of a company above the ICP's size).
- Anything the judge didn't pass, or scored below 4 on anything.
- Any draft from lean mode, which has no judge.
- Answers to questions, and any reply other than a booking link after a clear yes.
- Anything the lint script warned about on numbers or facts.

## Moving

The weekly report recommends moves (`scripts/edit_rate.py --ladder`). The human makes them by editing `autonomy.segments`. When a segment must move down, the report says so and the human removes it. Any complaint, or a spike in bounces or unsubscribes, means set everything back to level 2 and look at what happened.
