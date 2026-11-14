# The drafting pipeline

How one lead becomes one queued draft, or a hold, or an intro ask. `config.json` → `pipeline_mode` picks the mode: `full` (default) or `lean`. Paths are relative to the `outbound-core` folder.

## Full mode (default)

Each stage is a **separate call**: a subagent (the Agent/Task tool) given only the inputs listed. No stage sees more than it needs. The writer never sees raw research, and the judge never grades its own writing.

| # | Stage | Prompt | Gets only | Returns |
|---|---|---|---|---|
| 1 | Research | `engine/research.md` | the lead record, first-guess tier, `company/signals.md`, `company/offer.md` | research JSON |
| 2 | Selector | `engine/selector.md` | its Inputs list | a brief (`engine/brief-format.md`) |
| 3 | Writer | `engine/writer.md` | the brief, 3 to 5 examples from `scripts/voice.py pick`, `engine/message-standard.md`, `person/learned-rules.md` | a draft, or a hold |
| 4 | Cutter | `engine/cutter.md` | the draft, the brief's length budget, channel and touch, `person/learned-rules.md` | a shorter draft |
| 5 | Lint | `scripts/lint.py` | the draft plus the brief | pass or fail, with reasons |
| 6 | Judge | `engine/judge.md` | the draft, one replied-to example, `person/voice-bank.md`, `engine/message-standard.md`, the brief's facts | scores and a verdict |

**Saving usage.** Batch two or three leads per subagent call for the same stage, keeping each lead's inputs separate inside the call. Start every stage's subagent on Sonnet (pass `model: "sonnet"` when you start it). It's the kit's default for all stages, and it keeps usage low enough to run every weekday.

**What each outcome means:**
- **Selector says `hold`:** log a skip with the reason (`{"event": "skipped", "lead_id": "...", "email": "...", "reason": "hold: <reason>"}`). No draft.
- **Selector says `intro_first`:** queue an intro task instead of a draft (`review_queue.py task`, see the daily batch skill). No draft.
- **Writer returns `hold`:** log a skip (`"reason": "writer-hold: <why>"`).
- **Lint hard fail:** send the draft and the errors to the writer once, then cutter and lint again. A second fail: log a skip (`"reason": "lint"`).
- **Judge says `drop`:** log a skip (`"reason": "judge-creep"`). Don't retry.
- **Judge says `revise`:** one rewrite. Send the writer its draft plus `weakest_line`, `suggested_cut` and any `unsupported` claims, then cutter, lint and judge again. If the fact check still fails, log a skip (`"reason": "judge-facts"`). Any other second `revise`: queue it with the judge's result attached, so the human sees why. It can never auto-send.

## Lean mode (budget setting)

For smaller Claude plans. Fewer calls per lead, less checking. Lean drafts always wait for the human, at any autonomy level.

| # | Stage | Prompt | Gets only | Returns |
|---|---|---|---|---|
| 1 | Research | `engine/research.md` | same as full | research JSON |
| 2 | Select and write | `engine/lean.md` | everything the selector and writer get | a brief and a draft |
| 3 | Lint | `scripts/lint.py` | the draft plus the brief | pass or fail |

On a lint hard fail, run stage 2 once more with the errors. A second fail is a skip (`"reason": "lint"`). Holds and intro asks work the same as in full mode.

## After the pipeline (both modes)

Queue the draft with `scripts/review_queue.py add`. It lints again on the way in and refuses hard fails, so nothing broken reaches the human. Once the day's drafts are queued, run `scripts/lint.py --batch <today>` to catch sameness across the batch (shared openers, closers or repeated phrases). Rewrite the drafts it flags, starting with the most repeated, and re-queue them with `review_queue.py replace`.
