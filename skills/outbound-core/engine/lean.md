# Lean prompt (select and write in one call)

Used only when `config.json` → `pipeline_mode` is `lean`. You do the selector's job and the writer's job in one pass. There's no cutter and no judge after you, so be strict with yourself. Lean drafts never send without human approval, at any autonomy level.

## Inputs
- Everything the selector gets (`engine/selector.md` → Inputs), including `engine/tiers.md`, `engine/sequence.md` and `engine/brief-format.md`.
- Everything the writer gets (`engine/writer.md` → Inputs), including `engine/message-standard.md`, the sender's example messages and `person/learned-rules.md`.

## Step 1: the brief
Follow `engine/selector.md` in full, including the hold and warm-path checks. If `route` isn't `direct`, return the brief alone.

## Step 2: the message
Follow `engine/writer.md`, using only the brief from step 1 and the examples. Then cut it yourself using steps 1 to 3 of `engine/cutter.md`, and check:
- Under `length_budget`?
- Their world in the first 12 words?
- One sentence of five words or fewer?
- Exactly one question, at the end, the one from the brief?
- No number that isn't in the brief, no dashes, plain text?

## Output
Return only this JSON:

```json
{"brief": { ... }, "draft": {"subject": "...", "body": "..."}}
```

If you're given lint errors, fix exactly those and change nothing else.
