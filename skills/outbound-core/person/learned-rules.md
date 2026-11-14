# Learned rules

Short rules learned from the sender's edits. The writer and the cutter follow them on every draft. A rule is added only when the same edit shows up in at least `learning.rule_evidence` (3) sent messages, and the file never holds more than `learning.max_learned_rules` (15). `scripts/learn.py add-rule` enforces both. When it's full, merge two rules or retire a stale one. Rules a script could check (a banned phrase) belong in `engine/banned.txt` instead. Aim for fewer rules each month, not more.

Format: the rule, why, then the date and the sends it came from.

## Rules
- [none yet]
