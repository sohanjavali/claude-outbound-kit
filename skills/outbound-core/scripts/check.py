#!/usr/bin/env python3
"""Install check. Run it after copying the skills, and again after onboarding.

Usage:
  python3 ~/.claude/skills/outbound-core/scripts/check.py

Checks Python, the skill folders, config.json, the core files, that the scripts run, and whether
onboarding has filled in the company and person files. Connectors can't be checked from a script:
the onboarding skill checks those inside Claude.
"""

import json
import re
import subprocess
import sys

from _common import CORE

SKILLS = ["onboarding", "daily-batch", "approval-sweep", "followups", "reply-triage", "weekly-report"]
ENGINE = ["message-standard.md", "sequence.md", "tiers.md", "autonomy.md", "banned.txt", "pipeline.md",
          "research.md", "brief-format.md", "selector.md", "writer.md", "cutter.md", "judge.md", "lean.md"]
COMPANY = ["icp.md", "signals.md", "offer.md", "claims.md", "personas.md", "angles.md", "crm.md"]
PERSON = ["voice-bank.md", "warm-paths.md", "learned-rules.md"]
SCRIPTS = ["lint.py", "log.py", "review_queue.py", "voice.py", "learn.py", "edit_rate.py", "kit_write.py", "crm_queue.py"]
CHOICES = {
    "lead_source": {"apollo", "paste"},
    "email_send_mode": {"send", "draft"},
    "email_provider": {"gmail", "outlook"},
    "crm": {"hubspot", "salesforce", "attio", "none"},
    "pipeline_mode": {"full", "lean"},
}

results = []


def check(ok, label, fix=""):
    results.append(ok)
    print(("  ok    " if ok else "  FAIL  ") + label + ("" if ok or not fix else f"\n        fix: {fix}"))


def note(label):
    print("  note  " + label)


def main():
    print("Outbound kit check\n")
    check(sys.version_info >= (3, 9), f"Python {sys.version.split()[0]} (needs 3.9+)", "install Python 3.9 or newer")

    skills_dir = CORE.parent
    for s in SKILLS:
        check((skills_dir / f"outbound-{s}" / "SKILL.md").exists(), f"skill outbound-{s}",
              f"copy the outbound-{s} folder into {skills_dir}")

    try:
        config = json.loads((CORE / "config.json").read_text())
        check(True, "config.json is valid JSON")
    except Exception as e:  # noqa: BLE001
        check(False, f"config.json: {e}", "restore config.json from the kit download")
        config = {}
    for key, allowed in CHOICES.items():
        if config:
            # Installs from before lead_source existed keep their config on update, and they pull from Apollo.
            value = config.get(key, "apollo") if key == "lead_source" else config.get(key)
            check(value in allowed, f"config {key} = {value!r}",
                  f"set it to one of {sorted(allowed)}")
    if config:
        auto = config.get("autonomy", {})
        lvl = auto.get("default_level")
        check(lvl in (1, 2, 3, 4), f"config autonomy.default_level = {lvl!r}", "set it to 1, 2, 3 or 4")
        segs = auto.get("segments", {})
        check(isinstance(segs, dict) and all(v in (1, 2, 3, 4) for v in segs.values()),
              f"config autonomy.segments = {segs!r}", 'use {"segment name": level}, levels 1 to 4')
        seq = config.get("sequence", {})
        spacing = seq.get("spacing_days")
        check(isinstance(spacing, list) and spacing and all(isinstance(d, int) for d in spacing)
              and 1 <= seq.get("max_touches", 0) <= 5,
              f"config sequence = {seq.get('max_touches')} touches on days {spacing}",
              "max_touches 1 to 5, spacing_days a list like [0, 4, 8]")
        missing = [k for k in ("email", "email_followup", "linkedin", "linkedin_followup", "linkedin_connect")
                   if k not in config.get("limits", {})]
        check(not missing, "config limits" + (f" (missing {', '.join(missing)})" if missing else ""),
              "restore the limits block from the kit download")
        vol = config.get("volume", {})
        check(0 < vol.get("new_leads_per_day", 0) <= vol.get("max_new_leads_per_day", 0),
              f"config volume = {vol.get('new_leads_per_day')} a day (max {vol.get('max_new_leads_per_day')})",
              "new_leads_per_day must be between 1 and max_new_leads_per_day")

    for folder, names in (("engine", ENGINE), ("company", COMPANY), ("person", PERSON), ("scripts", SCRIPTS)):
        missing = [n for n in names if not (CORE / folder / n).exists()]
        check(not missing, f"{folder}/ files" + (f" (missing {', '.join(missing)})" if missing else ""),
              "restore the missing files from the kit download")

    state = CORE / "state"
    try:
        state.mkdir(exist_ok=True)
        probe = state / ".write-test"
        probe.write_text("ok")
        probe.unlink()
        check(True, "state/ is writable")
    except OSError as e:
        check(False, f"state/ is not writable: {e}", "check the folder permissions")

    sample = {"channel": "linkedin", "touch": 1, "body": "Saw the new shop. Worth a look?"}
    proc = subprocess.run([sys.executable, str(CORE / "scripts" / "lint.py"), json.dumps(sample)],
                          capture_output=True, text=True)
    check(proc.returncode in (0, 1) and '"pass"' in proc.stdout, "lint.py runs",
          proc.stderr.strip()[:200] or "run lint.py by hand to see the error")
    proc = subprocess.run([sys.executable, str(CORE / "scripts" / "log.py"), "report", "--days", "1"],
                          capture_output=True, text=True)
    check(proc.returncode == 0, "log.py report runs", proc.stderr.strip()[:200])

    claims = (CORE / "company" / "claims.md")
    if claims.exists():
        text = claims.read_text().lower().replace("’", "'")
        heads = [h for h in ("## approved claims", "## clients we can't name", "## never say") if h not in text]
        check(not heads, "claims.md headings" + (f" (missing {', '.join(heads)})" if heads else ""),
              "keep these headings exactly; the lint script reads them")

    proc = subprocess.run([sys.executable, str(CORE / "scripts" / "log.py"), "unconfirmed"], capture_output=True, text=True)
    if proc.returncode == 0 and json.loads(proc.stdout or "[]"):
        note("some sends were claimed but never confirmed; check the Sent folder (log.py unconfirmed)")

    unfilled = [f"{folder}/{n}" for folder, names in (("company", COMPANY), ("person", PERSON))
                for n in names if (CORE / folder / n).exists()
                and re.search(r"^\s*(-|\|)?\s*\[|\]: \[|\*\* \[", (CORE / folder / n).read_text(), re.M)
                and n != "learned-rules.md"]
    if unfilled:
        note("onboarding hasn't filled in: " + ", ".join(unfilled) + ' (say "set up the outbound agent")')
    if not (CORE / "person" / "examples.jsonl").exists():
        note("no voice bank yet (onboarding builds it from your sent mail)")
    if config.get("sender", {}).get("email", "") == "":
        note("sender.email is empty in config.json (onboarding fills it in)")

    print()
    if all(results):
        print("All checks passed.")
        return 0
    print(f"{results.count(False)} check(s) failed.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
