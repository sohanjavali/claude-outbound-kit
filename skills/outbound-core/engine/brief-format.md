# Brief format

The selector writes the brief from the full research. The writer sees only the brief, a few of the sender's real messages, the message standard and the learned rules. If something isn't in the brief, it doesn't go in the message. Every field is a note to the writer, not finished copy.

```json
{
  "lead_id": "string",
  "first_name": "Dana",
  "company": "Acme Plumbing",
  "title": "Owner",
  "channel": "email | linkedin | linkedin_connect",
  "touch": 1,
  "tier": "A | B | C",
  "segment": "a persona name from personas.md",
  "angle": "an angle name from angles.md",
  "route": "direct | intro_first | hold",
  "senior": false,
  "hold_reason": "why, if route is hold or intro_first, else empty",
  "intro_via": "the person who could introduce us, if intro_first, else null",
  "shared_context": {"text": "what we have in common", "from": "warm-paths.md, CRM or a sourced URL"},
  "detail": {"fact": "the one fact that opens the message", "source": "https://..."},
  "guess": "the likely problem, as a guess, max 15 words",
  "question": "the one closing question",
  "rung": "insight_give | custom_give | meeting_ask",
  "include_product": false,
  "product_line": "what the offer gives them, if include_product, else empty",
  "proof": "an approved claim copied word for word from claims.md, or null",
  "asset": {"title": "a value asset from offer.md", "url": "https://..."},
  "facts": [{"fact": "every fact the message may use", "source": "https://..."}],
  "length_budget": 80,
  "carries": "number | link | null",
  "register": "two words, like plain peer",
  "avoid": ["anything the writer must not say for this lead"],
  "previous_touches": ["the exact text of earlier touches, oldest first"],
  "reason_for_reviewer": "one line shown in the review file: why this person, why now"
}
```

## Field rules

- **route**: `hold` means don't write. `intro_first` means queue an intro ask instead of a cold draft. The writer only ever gets `direct` briefs.
- **senior**: true when the person is above the seniority ceiling in `icp.md`, or is a VP, C-level or founder. A senior first touch never sends without the human, at any autonomy level.
- **shared_context**: tier A only, and it opens the message. Null otherwise.
- **detail**: exactly one fact, from the research `facts` with its source, never from `unverified`. It must tie to a problem the offer solves. A fact that doesn't is just trivia: drop it. If there's no good fact, a short honest note with no fact is allowed, and `detail` is null.
- **guess**: opens with "My guess is", "Not sure if" or "Curious whether". Something they could correct.
- **question**: one, answerable in a line. On touch 1 it's about their world, never about a meeting. From touch 3 it can be an interest question with an easy out.
- **include_product**: false on touch 1 for tiers B and C. True on touch 3, for tier A when natural, or when they asked.
- **proof**: only if the customer or result looks like the reader. Never name a customer bigger or more senior than them.
- **asset**: on touch 2 (or 3 if the arc moved), one value asset from `offer.md`. Null otherwise.
- **facts**: every fact the message may use, with its number if it has one. The lint script allows only numbers found in the brief or in `claims.md`.
- **length_budget**: from `sequence.md` for this channel and touch. Set `carries` when the message carries a sourced number or a link, which allows up to 25 more words.
- **previous_touches**: so a follow-up says something new instead of repeating itself.
