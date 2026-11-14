"""Tiny tests for the outbound-core scripts. Run from the repo root:

    python3 -m unittest discover tests
"""

import datetime
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = pathlib.Path(__file__).resolve().parent.parent
SKILLS = REPO / "skills"

GOOD_EMAIL = (
    "Hi Dana,\n\nYou opened a second shop in Dayton in September. More trucks usually means more quotes "
    "to chase. My guess is the ones that go quiet are where jobs slip away.\n\nThat gap is fixable. "
    "We draft those follow-ups each morning, in your words, and you approve them.\n\n"
    "Is chasing quotes something you'd want off your plate?\n\nSohan"
)
BRIEF = {"detail": {"fact": "Opened a second shop in Dayton in September 2026", "source": "https://example.com"}}
TODAY = datetime.date.today()


def ago(days, hour=9):
    return (TODAY - datetime.timedelta(days=days)).isoformat() + f"T{hour:02d}:00:00"


class ScriptTest(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        shutil.copytree(SKILLS, self.tmp / "skills")
        self.core = self.tmp / "skills" / "outbound-core"
        (self.core / "company" / "claims.md").write_text(
            "# Claims\n\n## Approved claims\n- Owners save about 12 hours a month\n\n"
            "## Clients we can name\n- [client]\n\n## Clients we can't name\n- Globex\n\n"
            "## Never say\n- guaranteed results\n")
        self.env = dict(os.environ, OUTBOUND_CORE=str(self.core))

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def config(self, **changes):
        path = self.core / "config.json"
        cfg = json.loads(path.read_text())
        for dotted, value in changes.items():
            node = cfg
            *parents, last = dotted.split("__")
            for p in parents:
                node = node[p]
            node[last] = value
        path.write_text(json.dumps(cfg))

    def run_script(self, name, *args, stdin=None):
        return subprocess.run([sys.executable, str(self.core / "scripts" / name), *args],
                              input=stdin, capture_output=True, text=True, env=self.env)

    def out(self, name, *args, stdin=None):
        p = self.run_script(name, *args, stdin=stdin)
        self.assertIn(p.returncode, (0, 1), p.stderr)
        return json.loads(p.stdout)

    def lint(self, **draft):
        base = {"channel": "email", "touch": 1, "subject": "second shop", "body": GOOD_EMAIL, "brief": BRIEF}
        p = self.run_script("lint.py", json.dumps({**base, **draft}))
        return p.returncode, json.loads(p.stdout)

    def log_add(self, **event):
        p = self.run_script("log.py", "add", json.dumps(event))
        self.assertEqual(p.returncode, 0, p.stderr)
        return json.loads(p.stdout)

    def sent(self, qid, email, days_ago, touch=1, channel="email", **kw):
        return self.log_add(event="sent", id=qid, email=email, channel=channel, touch=touch,
                            kind="new" if touch == 1 else "followup", body="hi", draft="hi", at=ago(days_ago), **kw)

    def draft(self, **kw):
        d = {"lead": {"id": "L1", "name": "Dana Smith", "email": "dana@acme.com", "company": "Acme Plumbing"},
             "channel": "email", "touch": 1, "tier": "B", "segment": "owners", "angle": "quotes",
             "subject": "second shop", "body": GOOD_EMAIL, "brief": BRIEF,
             "judge": {"verdict": "pass", "scores": {"voice": 4}}}
        d.update(kw)
        return json.dumps(d)

    def queue(self, date=None, **kw):
        args = ["add"] + (["--date", date] if date else [])
        return self.run_script("review_queue.py", *args, stdin=self.draft(**kw))

    def md(self, date):
        return self.core / "state" / "queue" / f"{date}.md"


class TestLint(ScriptTest):
    def test_good_email_passes(self):
        code, out = self.lint()
        self.assertEqual(code, 0, out)

    def test_hard_fails(self):
        cases = {
            "dash": GOOD_EMAIL.replace("in September.", "in September - nice."),
            "question marks": GOOD_EMAIL.replace("in September.", "in September?"),
            "banned phrase": GOOD_EMAIL.replace("That gap is fixable.", "Hope this finds you well."),
            "number": GOOD_EMAIL.replace("More trucks", "Over 40 trucks"),
            "can't name": GOOD_EMAIL.replace("That gap is fixable.", "Globex fixed it."),
            "never-say": GOOD_EMAIL.replace("That gap is fixable.", "Guaranteed results."),
            "isn't at the end": GOOD_EMAIL.replace("\n\nSohan", " Either way, good luck with the new shop this year.\n\nSohan"),
            "markdown": GOOD_EMAIL.replace("\n\nThat gap", "\n\n- That gap"),
            "over the cap": GOOD_EMAIL.replace("Sohan", "word " * 40 + "\nSohan"),
            "placeholder": GOOD_EMAIL.replace("Hi Dana", "Hi {{first_name}}"),
        }
        for expect, body in cases.items():
            code, out = self.lint(body=body)
            self.assertEqual(code, 1, expect)
            self.assertTrue(any(expect in h for h in out["hard"]), (expect, out["hard"]))

    def test_meeting_ask_only_blocked_on_touch_one(self):
        body = GOOD_EMAIL.replace("Is chasing quotes something you'd want off your plate?", "Open to a quick call?")
        self.assertEqual(self.lint(body=body)[0], 1)
        self.assertEqual(self.lint(body=body, touch=2, kind="followup")[0], 0)

    def test_numbers_keep_their_units(self):
        self.assertEqual(self.lint(body=GOOD_EMAIL.replace("More trucks", "Saving 12 hours a month"))[0], 0)
        code, out = self.lint(body=GOOD_EMAIL.replace("More trucks", "A 12% lift"))
        self.assertEqual(code, 1, out)
        self.assertEqual(self.lint(body=GOOD_EMAIL.replace("in September", "in September 2025, with 2 trucks"))[0], 0)

    def test_urls_dont_trip_numbers_or_questions(self):
        reply = {"kind": "reply", "touch": 2, "subject": "", "brief": {},
                 "body": "Great, grab any time here: https://calendly.com/sohan/30min?ref=1\n\nSohan"}
        code, out = self.lint(**reply)
        self.assertEqual(code, 0, out)

    def test_number_rules_edge_cases(self):
        code, out = self.lint(body=GOOD_EMAIL + "\nPS: 73% faster replies.")
        self.assertEqual(code, 1, out)
        reply = {"kind": "reply", "touch": 2, "subject": "", "brief": {},
                 "body": "Sure, does Tuesday at 10:30 work for you?\n\nSohan"}
        self.assertEqual(self.lint(**reply)[0], 0)
        brief = dict(BRIEF, facts=[{"fact": "Raised $1.2 million in August", "source": "https://x.com"}])
        self.assertEqual(self.lint(brief=brief, body=GOOD_EMAIL.replace("More trucks", "After the $1.2M raise, more trucks"))[0], 0)
        made_up = dict(BRIEF, guess="My guess is 40 quotes a week slip")
        self.assertEqual(self.lint(brief=made_up, body=GOOD_EMAIL.replace("More trucks", "About 40 trucks"))[0], 1)

    def test_followup_cap_is_shorter(self):
        body = GOOD_EMAIL.replace("Is chasing", "word " * 20 + "Is chasing")
        self.assertEqual(self.lint(body=body)[0], 0)
        self.assertEqual(self.lint(body=body, touch=2, kind="followup")[0], 1)

    def test_connection_note_char_cap(self):
        self.assertEqual(self.lint(channel="linkedin_connect", subject="", body="Saw the Dayton shop. " * 5)[0], 0)
        self.assertEqual(self.lint(channel="linkedin_connect", subject="", body="Saw the Dayton shop. " * 20)[0], 1)

    def test_batch_sameness(self):
        date = "2026-10-20"
        for i in range(6):
            self.queue(date, lead={"id": f"L{i}", "name": f"P{i}", "email": f"p{i}@co{i}.com"})
        out = self.out("lint.py", "--batch", date)
        self.assertEqual(out["items"], 6)
        self.assertEqual(len(out["flagged_ids"]), 5)


class TestLog(ScriptTest):
    def test_empty_report(self):
        p = self.run_script("log.py", "report", "--days", "1")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("No activity in this period.", p.stdout)

    def test_spacing_and_stops(self):
        self.sent("q1", "dana@acme.com", 3, angle="quotes", segment="owners", tier="B")
        self.assertEqual(self.out("log.py", "due"), [])  # touch 2 is day 4, not day 3
        self.sent("q2", "sam@b.com", 4)
        self.assertEqual([d["email"] for d in self.out("log.py", "due")], ["sam@b.com"])
        self.log_add(event="meeting", email="sam@b.com")
        self.assertEqual(self.out("log.py", "due"), [])

    def test_seen_and_report(self):
        self.sent("q1", "dana@acme.com", 5, angle="quotes", segment="owners", tier="B")
        seen = self.out("log.py", "seen", "acme.com")
        self.assertTrue(seen["hold"])
        self.assertEqual(seen["colleagues_contacted_recently"], ["dana@acme.com"])
        self.log_add(event="skipped", lead_id="x", email="sam@gmail.com", reason="no-verified-email")
        self.assertFalse(self.out("log.py", "seen", "pat@gmail.com")["hold"])
        self.log_add(event="reply", email="dana@acme.com", category="positive")
        rep = self.out("log.py", "report", "--days", "7", "--json")
        self.assertEqual(rep["totals"]["positive_replies"], 1)
        self.assertEqual(rep["by"]["angle"]["quotes"]["positive"], 1)

    def test_claim_is_once_and_capped(self):
        self.config(volume__max_sends_per_day=1)
        self.assertTrue(self.out("log.py", "claim", "a")["ok"])
        self.assertFalse(self.out("log.py", "claim", "a")["ok"])
        self.assertIn("cap", self.out("log.py", "claim", "b")["why"])
        self.assertEqual(self.out("log.py", "unconfirmed"), [])  # too fresh: another run may be mid-send
        self.assertEqual([u["id"] for u in self.out("log.py", "unconfirmed", "--older-than", "0")], ["a"])
        self.out("log.py", "release", "a")
        self.assertTrue(self.out("log.py", "claim", "b")["ok"])
        self.assertFalse(self.out("log.py", "claim", "c")["ok"])  # b's open claim counts toward the cap

    def test_drafts_count_toward_the_cap(self):
        self.config(volume__max_sends_per_day=1)
        self.log_add(event="sent", id="d1", email="a@b.com", channel="email", touch=1, kind="new",
                     body="hi", draft="hi", mode="draft")
        self.assertFalse(self.out("log.py", "claim", "d2")["ok"])

    def test_restarted_sequence_and_forever_holds(self):
        self.sent("old1", "dana@acme.com", 120)
        self.sent("old2", "dana@acme.com", 116, touch=2)
        self.sent("new1", "dana@acme.com", 4)
        due = self.out("log.py", "due")
        self.assertEqual([(d["next_touch"], len(d["previous_touches"])) for d in due], [(2, 1)])
        self.sent("x1", "pat@zed.com", 120)
        self.log_add(event="reply", email="pat@zed.com", category="not-interested", at=ago(119))
        self.assertTrue(self.out("log.py", "seen", "pat@zed.com")["hold"])

    def test_connection_note_continues_as_linkedin(self):
        self.sent("c1", "dana@acme.com", 5, channel="linkedin_connect", mode="manual")
        d = self.out("log.py", "due")[0]
        self.assertEqual((d["channel"], d["needs_checkin"]), ("linkedin", True))

    def test_duplicate_sent_is_ignored(self):
        self.sent("q1", "a@b.com", 0)
        self.assertTrue(self.sent("q1", "a@b.com", 0)["duplicate"])

    def test_linkedin_needs_a_checkin(self):
        self.sent("q1", "dana@acme.com", 5, channel="linkedin", mode="manual")
        self.assertTrue(self.out("log.py", "due")[0]["needs_checkin"])
        self.log_add(event="checkin", email="dana@acme.com", channel="linkedin", replied=False)
        self.assertFalse(self.out("log.py", "due")[0]["needs_checkin"])

    def test_rejects_bad_event(self):
        self.log_add(event="reply", email="a@b.com", category="engaged")
        self.assertNotEqual(self.run_script("log.py", "add", json.dumps({"event": "reply", "email": "a@b.com", "category": "maybe"})).returncode, 0)
        self.assertNotEqual(self.run_script("log.py", "add", json.dumps({"event": "sent", "email": "a@b.com"})).returncode, 0)


class TestReviewQueue(ScriptTest):
    def test_add_approve_parse_mark(self):
        date = TODAY.isoformat()
        p = self.queue(date)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        qid = json.loads(p.stdout)["id"]
        self.assertEqual(self.out("review_queue.py", "parse"), [])
        md = self.md(date)
        md.write_text(md.read_text().replace("status: pending", "status: ✅️ looks good").replace("Hi Dana,", "Hey Dana,"))
        out = self.out("review_queue.py", "parse")
        self.assertEqual((len(out), out[0]["decision"], out[0]["edited"], out[0]["blocked"]), (1, "approve", True, None))
        self.assertTrue(out[0]["body"].startswith("Hey Dana,"))
        self.out("review_queue.py", "mark", qid, "sent")
        self.assertEqual(self.out("review_queue.py", "parse"), [])

    def test_old_queue_still_parsed(self):
        friday = (TODAY - datetime.timedelta(days=3)).isoformat()
        self.queue(friday)
        md = self.md(friday)
        md.write_text(md.read_text().replace("status: pending", "status: approved!"))
        self.assertEqual(len(self.out("review_queue.py", "parse")), 1)

    def test_full_mode_needs_a_judge(self):
        p = self.queue(judge=None)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("judge", p.stderr)
        self.config(pipeline_mode="lean")
        self.assertEqual(self.queue(judge=None).returncode, 0)

    def test_x_does_not_approve(self):
        date = TODAY.isoformat()
        self.queue(date)
        md = self.md(date)
        md.write_text(md.read_text().replace("status: pending", "status: X"))
        self.assertEqual(self.out("review_queue.py", "parse"), [])
        self.assertEqual(len(self.out("review_queue.py", "summary")["unrecognized_statuses"]), 1)

    def test_set_copies_a_decision_and_close_frees_the_thread(self):
        qid = json.loads(self.queue().stdout)["id"]
        self.out("review_queue.py", "set", qid, "✅")
        self.assertEqual(self.out("review_queue.py", "parse")[0]["decision"], "approve")
        self.out("review_queue.py", "close", qid, "blocked: they replied")
        self.assertEqual(self.out("review_queue.py", "parse"), [])
        self.assertEqual(self.queue().returncode, 0)  # the lead isn't stuck behind the closed item

    def test_one_person_per_company_unless_referral(self):
        self.assertEqual(self.queue().returncode, 0)
        other = {"id": "L2", "name": "Jo Smith", "email": "jo@acme.com"}
        self.assertNotEqual(self.queue(lead=other).returncode, 0)
        self.assertEqual(self.queue(lead=other, referral=True).returncode, 0)

    def test_missing_close_marker_keeps_the_edit(self):
        date = TODAY.isoformat()
        self.queue(date)
        md = self.md(date)
        md.write_text(md.read_text().replace("status: pending", "status: ✅").replace("Hi Dana,", "Hey Dana,")
                      .replace("<!-- /message -->\n", ""))
        self.assertTrue(self.out("review_queue.py", "parse")[0]["body"].startswith("Hey Dana,"))

    def test_no_duplicates_across_days_but_channels_are_separate(self):
        self.assertEqual(self.queue((TODAY - datetime.timedelta(days=1)).isoformat()).returncode, 0)
        self.assertNotEqual(self.queue().returncode, 0)
        p = self.queue(channel="linkedin", subject="", body="Saw the Dayton shop. My guess is quotes slip. "
                       "Is chasing them a pain right now?")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_blocked_after_a_reply(self):
        date = TODAY.isoformat()
        self.queue(date)
        md = self.md(date)
        md.write_text(md.read_text().replace("status: pending", "status: ✅"))
        self.log_add(event="reply", email="dana@acme.com", category="not-interested")
        self.assertIn("replied", self.out("review_queue.py", "parse")[0]["blocked"])

    def test_unrecognized_status_is_reported(self):
        date = TODAY.isoformat()
        self.queue(date)
        md = self.md(date)
        md.write_text(md.read_text().replace("status: pending", "status: hmm maybe"))
        self.assertEqual(len(self.out("review_queue.py", "summary")["unrecognized_statuses"]), 1)

    def test_refuses_hard_fail(self):
        p = self.queue(body=GOOD_EMAIL.replace(".", " — ", 1))
        self.assertEqual(p.returncode, 1)
        self.assertFalse(json.loads(p.stdout)["queued"])

    def test_priority_and_tasks_go_first(self):
        date = TODAY.isoformat()
        self.queue(date)
        reply = self.draft(lead={"id": "L2", "name": "Sam Lee", "email": "sam@b.com"}, kind="reply", touch=1,
                           priority=True, body="Great, here's a link to grab a time: https://cal.com/x/30\n\nSohan")
        self.assertEqual(self.run_script("review_queue.py", "add", stdin=reply).returncode, 0)
        task = {"lead": {"name": "Raj Patel"}, "task_type": "intro", "task": "Ask Raj for an intro to Pat", "priority": True}
        self.assertEqual(self.run_script("review_queue.py", "task", stdin=json.dumps(task)).returncode, 0)
        text = self.md(date).read_text()
        self.assertLess(text.index("Sam Lee"), text.index("Dana Smith"))
        self.assertLess(text.index("TASK"), text.index("Dana Smith"))

    def test_replace_only_untouched(self):
        date = TODAY.isoformat()
        qid = json.loads(self.queue(date).stdout)["id"]
        new = {"body": GOOD_EMAIL.replace("That gap is fixable.", "Easy fix.")}
        self.assertEqual(self.run_script("review_queue.py", "replace", qid, json.dumps(new)).returncode, 0)
        self.assertIn("Easy fix.", self.md(date).read_text())
        md = self.md(date)
        md.write_text(md.read_text().replace("Easy fix.", "Simple fix."))
        self.assertNotEqual(self.run_script("review_queue.py", "replace", qid, json.dumps(new)).returncode, 0)

    def test_auto_approval_decided_at_queue_time(self):
        self.config(autonomy__segments={"owners": 3}, autonomy__spot_check_rate=0)
        judge = {"verdict": "pass", "scores": {"voice": 4, "creep": 5}}
        out = json.loads(self.queue(judge=judge).stdout)
        self.assertTrue(out["auto"])
        out = json.loads(self.queue(lead={"id": "L9", "email": "x@y.com"}, judge=judge,
                                    brief=dict(BRIEF, senior=True)).stdout)
        self.assertFalse(out["auto"])
        self.assertEqual(self.out("review_queue.py", "parse", "--include-pending")[0]["decision"], "auto")


class TestVoice(ScriptTest):
    def test_build_and_pick(self):
        corpus = self.tmp / "sent.jsonl"
        long = "Thanks for the notes on the proposal, I'll fold them in and send a new version by Thursday. "
        corpus.write_text("\n".join(json.dumps(r) for r in [
            {"subject": "proposal", "body": long + "\n\nOn Mon, Oct 5, Sam wrote:\n> old text", "got_reply": True},
            {"subject": "dup", "body": long},
            {"subject": "Invoice 42", "body": "Attached is the invoice for September, due in thirty days as usual."},
            {"subject": "short", "body": "ok thanks"},
        ]))
        out = self.out("voice.py", "build", str(corpus))
        self.assertEqual((out["kept"], out["with_reply"]), (1, 1))
        picked = self.out("voice.py", "pick", "--n", "3", "--replied")
        self.assertEqual(len(picked), 1)
        self.assertNotIn("wrote:", picked[0]["body"])

    def test_import_linkedin(self):
        csv_path = self.tmp / "messages.csv"
        csv_path.write_text(
            "CONVERSATION ID,FROM,DATE,CONTENT\n"
            "c1,Sohan Javali,2026-01-01,Hey Sam saw your post on hiring reps this spring and had one idea for you\n"
            "c1,Sam Lee,2026-01-02,Sure tell me more\n"
            "c2,Sohan Javali,2026-01-03,Hey Pat congrats on the new role at Acme this month and good luck with it\n")
        out = self.out("voice.py", "import-linkedin", str(csv_path), "--me", "Sohan Javali")
        self.assertEqual((out["kept"], out["with_reply"]), (2, 1))


class TestLearnAndEditRate(ScriptTest):
    def test_kills_count_and_rules_need_evidence(self):
        for i in range(3):
            self.log_add(event="sent", id=f"e{i}", email=f"a{i}@b.com", channel="email", touch=1, kind="new",
                         segment="owners", draft="Hi Sam, one two three. Worth a look?",
                         body="Hey Sam, one two three. Worth a look?")
        self.log_add(event="sent", id="u1", email="c@d.com", channel="email", touch=1, kind="new",
                     segment="owners", draft="Same text?", body="Same text?")
        self.log_add(event="killed", id="k1", email="e@f.com", touch=1, segment="owners")
        out = self.out("learn.py", "ingest")
        self.assertEqual((out["ingested"], out["edited"]), (4, 3))
        self.assertEqual(self.out("learn.py", "ingest")["ingested"], 0)

        rates = self.out("edit_rate.py", "--by", "segment")["owners"]
        self.assertEqual((rates["reviewed"], rates["untouched"], rates["killed"]), (5, 1, 1))

        (self.core / "person" / "learned-rules.md").write_text("# Learned rules\n\n## Rules\n- [none yet]\n")
        p = self.run_script("learn.py", "add-rule", "Open with Hey", "--why", "always changed", "--evidence", "e0", "u1")
        self.assertEqual(p.returncode, 1)
        p = self.run_script("learn.py", "add-rule", "Open with Hey", "--why", "always changed",
                            "--evidence", "e0", "e1", "e2")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(self.out("learn.py", "rules")["count"], 1)
        self.assertEqual(self.run_script("learn.py", "retire", "Open with").returncode, 0)


class TestKitWriteAndDraftMode(ScriptTest):
    def test_kit_write_only_allowed_paths(self):
        ok = self.run_script("kit_write.py", "state/reports/2026-10-20.md", stdin="# Report\n")
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertTrue((self.core / "state" / "reports" / "2026-10-20.md").exists())
        self.assertNotEqual(self.run_script("kit_write.py", "scripts/lint.py", stdin="x").returncode, 0)
        self.assertNotEqual(self.run_script("kit_write.py", "../../etc.md", stdin="x").returncode, 0)
        self.assertNotEqual(self.run_script("kit_write.py", "config.json", stdin="{not json").returncode, 0)

    def test_draft_mode_waits_for_the_real_send(self):
        self.log_add(event="sent", id="d1", email="dana@acme.com", channel="email", touch=1, kind="new",
                     body="hi", draft="hi", mode="draft", at=ago(6))
        self.assertEqual(self.out("log.py", "due"), [])  # still sitting in Drafts
        self.assertEqual([u["id"] for u in self.out("log.py", "undelivered")], ["d1"])
        self.log_add(event="delivered", id="d1", at=ago(2))
        self.assertEqual(self.out("log.py", "due"), [])  # sent 2 days ago, touch 2 is day 4
        self.assertTrue(self.log_add(event="delivered", id="d1", at=ago(2))["duplicate"])
        self.log_add(event="sent", id="d2", email="sam@b.com", channel="email", touch=1, kind="new",
                     body="hi", draft="hi", mode="draft", at=ago(9))
        self.log_add(event="delivered", id="d2", at=ago(4))
        self.assertEqual([d["email"] for d in self.out("log.py", "due")], ["sam@b.com"])


class TestCrmQueue(ScriptTest):
    def test_queue_apply_once(self):
        upd = {"action": "send", "email": "Dana@Acme.com", "ref": "q1", "do": "create contact, log email"}
        first = self.out("crm_queue.py", "add", stdin=json.dumps(upd))
        self.assertEqual(first["email"], "dana@acme.com")
        self.assertTrue(self.out("crm_queue.py", "add", stdin=json.dumps(upd))["duplicate"])
        self.out("crm_queue.py", "add", stdin=json.dumps({**upd, "action": "reply", "ref": "m9", "do": "deal"}))
        self.assertEqual(self.out("crm_queue.py", "pending", "--count"), {"pending": 2})
        self.out("crm_queue.py", "done", first["id"])
        self.assertEqual(self.out("crm_queue.py", "done", first["id"])["already"], "done")
        waiting = self.out("crm_queue.py", "pending")
        self.assertEqual([u["action"] for u in waiting], ["reply"])
        self.out("crm_queue.py", "skip", waiting[0]["id"], "handled by hand")
        self.assertEqual(self.out("crm_queue.py", "pending"), [])

    def test_task_date_is_normalized(self):
        u = self.out("crm_queue.py", "add", stdin=json.dumps(
            {"action": "send", "email": "a@b.com", "ref": "q9", "do": "log it", "next_task_date": "2026-10-29"}))
        self.assertEqual(u["next_task_due"], "2026-10-29")
        self.assertNotIn("next_task_date", u)
        self.assertNotEqual(self.run_script("crm_queue.py", "add", stdin=json.dumps(
            {"action": "task", "email": "a@b.com", "do": "x", "next_task_due": "next monday"})).returncode, 0)

    def test_rejects_bad_update(self):
        self.assertNotEqual(self.run_script("crm_queue.py", "add", stdin='{"action": "send", "email": "a@b.com"}').returncode, 0)
        self.assertNotEqual(self.run_script("crm_queue.py", "add", stdin='{"action": "x", "email": "a@b.com", "do": "y"}').returncode, 0)
        self.assertNotEqual(self.run_script("crm_queue.py", "done", "crm-99999").returncode, 0)


class TestNextDue(ScriptTest):
    def test_counts_from_the_real_send(self):
        self.log_add(event="sent", id="d1", email="dana@acme.com", channel="email", touch=1, kind="new",
                     body="hi", draft="hi", mode="draft", at="2026-10-20T23:00:00")
        self.assertIsNone(self.out("log.py", "next-due", "d1")["next_touch"])  # still in Drafts
        self.log_add(event="delivered", id="d1", at="2026-10-22T10:00:00")  # sent Thursday
        self.assertEqual(self.out("log.py", "next-due", "d1")["due"], "2026-10-26")  # Monday, not Friday
        self.log_add(event="sent", id="s1", email="sam@b.com", channel="email", touch=1, kind="new",
                     body="hi", draft="hi", mode="send", at="2026-10-19T09:00:00")  # Monday
        self.assertEqual(self.out("log.py", "next-due", "s1")["due"], "2026-10-23")
        self.log_add(event="sent", id="s3", email="sam@b.com", channel="email", touch=3, kind="followup",
                     body="hi", draft="hi", mode="send", at="2026-10-27T09:00:00")
        self.assertIsNone(self.out("log.py", "next-due", "s3")["next_touch"])
        self.log_add(event="reply", email="dana@acme.com", category="not-interested", at="2026-10-22T11:00:00")
        self.assertIsNone(self.out("log.py", "next-due", "d1")["next_touch"])  # replied: no touch 2 task


class TestCheck(ScriptTest):
    def test_check_passes_on_a_fresh_copy(self):
        p = self.run_script("check.py")
        self.assertEqual(p.returncode, 0, p.stdout)


if __name__ == "__main__":
    unittest.main()
