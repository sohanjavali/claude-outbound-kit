# Voice bank

Onboarding builds this from 20 or more of the sender's real sent emails (`scripts/voice.py build`), plus their LinkedIn message export if they use LinkedIn. The example messages themselves live in `examples.jsonl`. This file is the summary the judge uses to check voice.

## Sender
- **Name:** [name]
- **Role:** [role]
- **Sends from:** [email address]

## How they write
- **Typical length:** [e.g. 40 to 80 words]
- **Sentence length:** [e.g. short, 8 to 12 words]
- **How they open:** [e.g. "Hey Sam," or straight into the point with no greeting] (also `sender.greeting` in config.json)
- **How they sign off:** [e.g. "Thanks, Alex" or just "Alex"] (also `sender.signoff` in config.json)
- **Tone:** [e.g. casual, direct, a little dry]
- **Words they use a lot:** [list]
- **Punctuation:** [e.g. exclamation marks rarely, never semicolons]
- **Things they never do:** [e.g. exclamation marks, "Hope you're well"]

## Notes from onboarding
[Anything else the sender said about how they want to sound.]
