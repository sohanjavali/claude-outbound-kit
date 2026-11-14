# Holds and tiers

Every lead goes through the hold checks first. Then it gets a tier, which sets how much research it gets and how direct the message is. Tiers never relax the message standard.

## 1. Hold checks (before any paid lookup, and again before every follow-up)

Hold the lead, and don't write to them, if any of these is true:
- They're on the never-contact list (`company/crm.md`), or they unsubscribed or bounced before (`scripts/log.py seen`).
- Anyone on the team contacted them, or anyone at their company, within `volume.skip_if_contacted_within_days`. That includes a sequence still running and a draft still waiting in the queue.
- They have an open deal, or they're a current customer, partner or competitor (CRM and `company/icp.md`).
- They're above the seniority ceiling in `company/icp.md` for a cold first touch.
- They match a disqualifier in `company/icp.md`.
- There's nothing true and relevant to say. A hold is a real answer, not a failure.

Log a hold as a skip with its reason.

## 2. Warm path first

If `person/warm-paths.md` or the CRM shows a real route to them (someone who'd introduce you, a past conversation, a shared group where you're actually active), the better first move is usually an intro, not a cold note. The selector sets `route: intro_first` and names the person. The review file then gets an "ask for an intro" item instead of a cold draft.

## 3. Tiers

A first guess comes from the lead record, the CRM and `person/warm-paths.md` before research, to decide how deep research goes. The selector confirms it after research.

| Tier | Who | Research | Product on touch 1 | The question |
|---|---|---|---|---|
| **A, warm** | Engaged before: replied, met, came through a warm path, past conversation | Deepest. Lead with the shared context | Allowed if natural | Can be the most direct |
| **B, active** | A signal from `company/signals.md` fired within its freshness window, with a source | One signal-based fact | Out | A clear, easy question |
| **C, cold** | Matches the ICP, nothing else | Light. One sourced fact | Out | The softest question |

- Being in the same big online group isn't warm. Being known there is.
- When in doubt, pick the lower tier. A warm-sounding message to a cold lead reads as fake.
- Fill the day's batch in tier order (A, then B, then C) up to `volume.new_leads_per_day`.
