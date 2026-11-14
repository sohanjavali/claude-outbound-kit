# Message standard

The writer, the cutter and the judge all read this file. It's twelve principles, each with the reason behind it, and it stays at twelve: adding one means retiring one. Things a script can enforce (length, one question, banned phrases, numbers, dashes, plain text) live in `scripts/lint.py` and `banned.txt`, so this file says what to do, not what to avoid.

1. **One idea.** One thing you noticed, one guess about it, one question. *A second idea competes with the first, and people read these on a phone in a few seconds.*
2. **Their world in the first 12 words.** Open with their situation, not with us. "You opened a second shop in Kettering" beats "We help plumbers." *The preview line decides whether the rest gets read.*
3. **One concrete fact, stated plainly.** Say what they did and let it do the work. No compliments. *Praise from someone they've never met feels like a sales move. A plain fact shows you actually looked.*
4. **Guess, don't diagnose.** Name the likely problem as a guess they can correct: "My guess is", "Not sure if", "Curious whether". *Being guessed at invites a correction. Being told what's wrong with you invites a delete.*
5. **End on one easy question about their world.** Something they could answer in a line without deciding anything about us. On a first touch it's never about a meeting. *A direct question nudges people to answer. A statement gives them nothing to do.*
6. **Outcome before mechanism.** When the offer appears, say what they'd get, not how it works. *Nobody wants the machinery, they want the result. "Follow-ups drafted every morning" lands. "An AI research layer" doesn't.*
7. **The product is one plain sentence, never the first, and only when the brief says so.** *Lead with the product and the message gets filed as an ad.*
8. **Say it the way you'd say it out loud.** Short words, short sentences, and at least one sentence of five words or fewer. About a grade 6 reading level. *Plain wording feels honest. Sentences that all run the same length feel generated.*
9. **Sound like the sender.** Greeting, warmth, punctuation and sign-off come from their real messages. *If they never use exclamation marks, a draft with one isn't theirs.*
10. **Leave it a little unfinished.** No summary line, no tidy wrap-up, no matching paragraph lengths. *Neat, balanced messages look machine-made. Real notes are a bit uneven.*
11. **Cut anything the reader doesn't need,** including sentences whose only job is to show research was done. *Every word they skip is a word that made the message feel longer.*
12. **Never state what you couldn't verify.** Every fact comes from a sourced line in the brief. *One wrong fact costs more trust than ten right ones earn.*

## Format

- **Plain text.** No HTML, markdown, bullets, images or attachments. Commas and periods, never dashes.
- **Email subject:** two to four lowercase words about their world, never about the product. No "Re:" or "Fwd:" on a first touch. Follow-ups reply in the same thread and keep the subject.
- **Length:** a ceiling, not a target. Budgets per channel and touch are in `sequence.md` and `config.json` → `limits`.
- **Sign-off:** the sender's own, from `person/voice-bank.md`.

## Effort by warmth

The principles apply to every tier. What changes by tier is how deep research goes and how direct the question is (`tiers.md`).
