# Helpdesk Triage Agent

A small, read-only agent that triages IT service desk tickets. It reads a ticket, picks the best runbook, sets a priority, drafts a reply and decides whether a human must take over.

It is built the way a real service desk works: identity checks come first for account changes, security reports always escalate, and anything it is not sure about goes to a person.

All runbooks and tickets here are fictional. No employer data is used.

## What it does

| Step | What happens |
|---|---|
| Classify | Scores the ticket against each runbook's keywords and returns a category with a confidence score |
| Prioritise | P1 for outages, P2 for blocked users, P3 otherwise. Security words raise the priority |
| Safety rules | Password, MFA and lockout runbooks require identity verification. Security incidents always escalate |
| Reply | Drafts a short reply from the runbook steps. It never asks for passwords or MFA codes |
| Fallback | Low confidence tickets are marked `unclassified` and escalated to a human |
| Knowledge | `kb` turns a solved ticket into a knowledge article draft |

It works fully offline. If `ANTHROPIC_API_KEY` is set and you pass `--llm`, a model rewrites only the reply draft, and it is only given the runbook steps, so it cannot invent procedures.

## Quick start

```bash
pip install -r requirements.txt
pytest -q

python -m triage_agent.cli ticket "Locked out of my account" --description "Too many attempts, urgent"
python -m triage_agent.cli file data/sample_tickets.json
python -m triage_agent.cli kb "Reset MFA after a new phone" \
  --symptoms "User lost their phone" --step "Verify identity" --step "Register new method"

# optional API
uvicorn triage_agent.api:app --reload
curl -X POST localhost:8000/triage -H 'content-type: application/json' \
  -d '{"summary":"Printer offline","description":"queue stuck"}'
```

## ServiceNow connector (optional)

The agent can triage new incidents from a ServiceNow instance. Use a free
[Personal Developer Instance](https://developer.servicenow.com) with fake data.

```bash
set SN_INSTANCE=https://devXXXXX.service-now.com
set SN_USER=admin
set SN_PASSWORD=your-instance-password
python -m triage_agent.cli servicenow --limit 5           # dry run, prints only
python -m triage_agent.cli servicenow --limit 5 --apply   # adds work notes
```

Safety: dry run by default, HTTPS only, credentials from environment variables, and
the only field ever written is `work_notes`. It never changes state, priority,
assignment or category, and never touches accounts. Tests use a fake transport, so CI
needs no live instance.

## Layout

```
triage_agent/   agent, runbook loader, CLI, API, optional LLM step
runbooks/       one markdown file per category (edit these to change behaviour)
data/           fictional sample tickets
tests/          pytest suite
.github/        CI on Python 3.11 and 3.12
```

## Design choices

- **Read-only.** The agent never changes accounts. It suggests steps and flags what must be verified.
- **Runbooks as data.** Add a markdown file to add a category. No code changes.
- **Human in the loop.** Unknown, security and P1 tickets escalate.
- **LLM is optional and boxed in.** It can only reword; it cannot add steps.

## Limits

Keyword scoring is simple on purpose and easy to explain. A next step would be embeddings for retrieval, plus an evaluation set to measure classification accuracy.

## Licence

MIT
