# Setup instructions for Claude

These are for Claude, not the person. The person pasted one sentence asking you to install the outbound kit. They may never have used a terminal, so they shouldn't have to type a command, find a folder or install anything themselves. You do the work. They read what you tell them and click Allow.

## How to talk to them while you work

- **Before every action that will ask their permission, say in one plain sentence what it does and why.** For example: "Next I'll copy the kit's skills into Claude's skills folder, so Claude can use them. You'll see a box asking to allow it." Then give the action itself a plain-words description too, because that's what the permission box shows. Never let a box appear that you haven't explained.
- No jargon. Say "the kit's files" and "Claude's skills folder", not paths, unless they ask.
- **When a box offers "Always allow" for the kit's own scripts or connectors, tell them to pick it, and why:** later runs happen on a schedule when nobody's there to click. For anything else, a one-time Allow is fine.
- One step at a time. Tell them which step of five you're on.

## 1. Find the kit
Look in `~/Downloads` for a folder named `claude-outbound-kit` (Safari unzips downloads on its own) or a file named `claude-outbound-kit*.zip`. If there's only the zip, unzip it into `~/Downloads`. If there are several versions, use the newest and say which. If you can't find it, ask them where they saved the download; don't make them type a path, offer the likely places (Desktop, Documents) and look yourself.

From here, `$KIT` means that unzipped folder.

## 2. Make sure Python works
Run `python3 --version`.
- **Version 3.9 or newer:** go on.
- **A box pops up asking to install "command line developer tools"** (a fresh Mac does this the first time): tell them "A box from Apple just appeared. Click Install, then Agree. It takes a few minutes. Tell me when it says it's done." When they say so, run `python3 --version` again.
- **No box and no Python:** run `xcode-select --install` to make the box appear, explained first, then the same as above.
- **Windows or Linux:** walk them through installing Python 3 from python.org in plain steps, and check again.

## 3. Install the skills
In one command (one Allow), copy every `$KIT/skills/outbound-*` folder into `~/.claude/skills/`, creating it if needed.

**If `~/.claude/skills/outbound-core/` already exists, this is an update, not a fresh install.** Their company files, voice, settings and log live there. Copy the six other skill folders over, and update `outbound-core` without touching `config.json`, `company/`, `person/`, `state/` or `engine/banned.txt` (rsync with those excluded, as in `$KIT/INSTALL.md` under "Updating the kit"). Tell them their setup is kept.

## 4. Check the install
Run `python3 ~/.claude/skills/outbound-core/scripts/check.py`. Every line should say `ok` or `note`. Fix any `FAIL` yourself using the fix it prints, then run it again. Notes about unfilled files are expected: onboarding fills them.

## 5. Start onboarding
Tell them the install is done and setup comes next: about an hour, mostly you proposing answers and them saying yes or fixing them.

Then run the `outbound-onboarding` skill. If it isn't available yet (some versions of Claude Code only see new skills in a new conversation), read `~/.claude/skills/outbound-onboarding/SKILL.md` and follow it directly, the same way. Don't send them to open a new conversation unless that fails too.

Based on the public playbook design.
