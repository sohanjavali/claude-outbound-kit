# CRM conventions

How the kit records outreach in the CRM. Onboarding rewrites this for the CRM in use (`crm` in config.json: hubspot, salesforce, attio or none). With `none`, skip the CRM steps: the kit's own log is the record.

## CRM
[hubspot | salesforce | attio | none]

## Hold checks (before any draft)
- Skip anyone with an open deal or who is a current customer.
- Skip anyone that any rep on the team emailed or logged a note on within `volume.skip_if_contacted_within_days`.
- Skip anyone whose company another rep is actively working.

## On every send
- **Contact:** create or update it with name, email, company, title and LinkedIn URL.
- **Activity:** log the exact message sent, as an email activity on the contact.
- **Next task:** a follow-up task due on the next touch date, named "Touch N follow-up: <company>", with task type To-do (on HubSpot, `hs_task_type` = `TODO`; some accounts reject a task without a type). None after the last touch.
- **Status:** [e.g. lead status set to "Outreach" on first send]

## On a reply
- **Positive:** [e.g. lifecycle to "Opportunity", a deal named "[company] - setup" in pipeline [name], stage [name]]
- **Not now:** a task to revisit on the date they named, task type To-do
- **Not interested or unsubscribe:** [e.g. status "Do not contact"]

## Owner
[Who owns new contacts in the CRM.]

## Never contact
Emails or whole domains, one per bullet (a note after the address is fine). The daily batch skips these and `log.py seen` reports them.
- [email or domain]
