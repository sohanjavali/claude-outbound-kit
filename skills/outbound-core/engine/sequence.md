# Sequence rules

A sequence is every touch to one person, on one channel, about one reason for writing. Most people won't buy this quarter. With them the goal is to be the name they remember, and think well of, when the need finally comes up.

## Timing

- **3 touches by default, on days 0, 4 and 8** (`config.json` → `sequence.max_touches`, `sequence.spacing_days`). Count from the day touch 1 was actually sent.
- `max_touches` can go up to 5. Touches past the end of `spacing_days` come 4 days after the one before.
- **Text only.** No images, attachments or video files. A link is fine from touch 2 on, with a clause that says why it's worth opening.
- **Stop on any reply**, a booked meeting, a bounce or an unsubscribe. An out-of-office pushes the next touch to the day after they're back.
- **Email follow-ups reply in the same thread.**
- **After `volume.skip_if_contacted_within_days` (90), someone who never replied can come back as a new lead** with a fresh touch 1. Anyone who said no, unsubscribed or bounced never does.

## Length budgets (a ceiling, not a target)

| Channel and touch | Aim for | Hard cap |
|---|---|---|
| Email, touch 1 | 50 to 80 words | 90 |
| Email, follow-up | 35 to 65 words | 75 |
| LinkedIn connection note | a short note | 300 characters |
| LinkedIn message, touch 1 | 25 to 40 words | 50 |
| LinkedIn message, follow-up | 20 to 40 words | 45 |
| Email subject | 2 to 4 words | 5 |

A message that carries a sourced number or a link (with a clause saying why it matters) may run up to 25 words over. Extra words have to bring something new. Padding the same point doesn't count. Floors: never under 35 words for email or 20 for LinkedIn messages. Too short reads as a bot too. The exact numbers live in `config.json` → `limits`.

## The arc

| Touch | Day | Job | Product | Rung | The question |
|---|---|---|---|---|---|
| 1 | 0 | Earn a conversation: one fact, one guess, one question | Out | `insight_give` | About their world |
| 2 | 4 | Give something small and real: a number, a benchmark, or a value asset from `company/offer.md` | Out, or one clause | `insight_give` or `custom_give` | The same kind of easy question, from a different side |
| 3 | 8 | The product in one plain sentence, tied to what they'd care about | In | `meeting_ask` | Interest, with an easy way to say no. Word it fresh each time |
| 4 (optional) | 12 | Proof: one approved claim from `company/claims.md` that looks like them | In | `custom_give` | Interest |
| 5 (optional) | 16 | Close the loop politely and leave the door open | Optional | none | One last easy question |

Warm (tier A) leads can have the product in on touch 1 if the shared context makes it natural.

## The offer ladder

Every touch stands on one rung, set by the selector as `rung`:

| Rung | What the touch gives |
|---|---|
| `insight_give` | Something useful to anyone like them: a number, a pattern, a resource |
| `custom_give` | Something made for them: a quick teardown, a specific idea, a recommendation |
| `meeting_ask` | An invitation to talk or take a look |

- A cold touch 1 is never `meeting_ask`.
- Never the same rung twice in a row to someone who hasn't replied.
- Never three gives in a row: move to the ask, or stop.

## Follow-ups aren't bumps

Every follow-up brings something the last one didn't: a new number, a different question, or one plain line about the offer. Mention the earlier note in a few words at most; don't restate it. Phrases like "just following up" are in `banned.txt`.

## Before drafting any follow-up

1. Check for a reply from that person, or anyone at their company, since the last touch.
2. Re-run the hold checks in `tiers.md`: an open deal, someone else on the team now talking to them, or a new never-contact entry ends the sequence.
3. Look for news since the last touch. New, sourced news can be the fact for this touch.

## LinkedIn

- Every LinkedIn message is sent by hand. The kit drafts it, links the profile, and logs it when the human marks it sent.
- Cold, and not connected: touch 1 is a connection request with a short note (`linkedin_connect`). Touch 2 is a message once they accept.
- Warm, or already connected: message directly.
- The kit can't see LinkedIn replies. Each sent LinkedIn touch gets a check-in item in the review file ("Did they reply?") before the next touch is drafted.
