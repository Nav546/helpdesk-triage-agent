import json
from pathlib import Path

import pytest

from triage_agent import Ticket, TriageAgent
from triage_agent.agent import draft_kb_article
from triage_agent.runbooks import parse_runbook

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def agent():
    return TriageAgent()


def t(summary, description="", id="T-1"):
    return Ticket(id, summary, description)


def test_password_reset_requires_identity_verification(agent):
    r = agent.triage(t("Forgot my password", "it expired"))
    assert r.category == "password_reset"
    assert r.verify_identity is True
    assert "verify" in r.reply_draft.lower()
    assert "do not send us your password" in r.reply_draft.lower()


def test_mfa_reset_requires_two_checks(agent):
    r = agent.triage(t("New phone, authenticator missing"))
    assert r.category == "mfa_reset"
    assert r.verify_identity is True
    assert any("challenge question" in s for s in r.steps)


def test_security_always_escalates(agent):
    r = agent.triage(t("Suspicious email", "I clicked a link in a phishing email"))
    assert r.category == "security_incident"
    assert r.escalate is True
    assert any("security team" in s.lower() for s in r.steps)


def test_p1_outage_escalates(agent):
    r = agent.triage(t("All stores cannot trade", "outage, payment terminals down"))
    assert r.priority == "P1"
    assert r.escalate is True


def test_low_confidence_goes_to_human(agent):
    r = agent.triage(t("Need a meeting room booked"))
    assert r.category == "unclassified"
    assert r.escalate is True
    assert r.runbook is None


def test_priority_p3_default(agent):
    r = agent.triage(t("Printer is out of toner"))
    assert r.priority == "P3"


def test_security_keyword_raises_priority_inside_other_category(agent):
    r = agent.triage(t("Email problem", "weird email, possibly compromised mailbox"))
    assert r.escalate is True
    assert r.priority in ("P1", "P2")


def test_never_returns_credentials_request(agent):
    for d in json.loads((ROOT / "data" / "sample_tickets.json").read_text()):
        r = agent.triage(Ticket(**d))
        assert "send me your password" not in r.reply_draft.lower()


def test_sample_tickets_all_produce_a_result(agent):
    for d in json.loads((ROOT / "data" / "sample_tickets.json").read_text()):
        r = agent.triage(Ticket(**d))
        assert r.category
        assert r.priority in ("P1", "P2", "P3")
        assert 0.0 <= r.confidence <= 1.0


def test_runbook_parser_rejects_missing_front_matter():
    with pytest.raises(ValueError):
        parse_runbook("no front matter here")


def test_kb_article_contains_steps_and_review_note():
    kb = draft_kb_article("Reset MFA", "User lost phone", ["Verify", "Re-register"], "mfa_reset")
    assert "# Reset MFA" in kb
    assert "1. Verify" in kb
    assert "Review before publishing" in kb


def test_llm_polish_falls_back_without_key(agent, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    r = agent.triage(t("Forgot my password"), use_llm=True)
    assert r.reply_draft.startswith("Hi,")


def test_api_triage_endpoint():
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient
    from triage_agent.api import app

    c = TestClient(app)
    assert c.get("/health").json() == {"status": "ok"}
    res = c.post("/triage", json={"summary": "Printer offline", "description": "queue stuck"})
    assert res.status_code == 200
    assert res.json()["category"] == "printer"


def test_security_incident_is_at_least_p2(agent):
    r = agent.triage(t("Suspicious email, I clicked a link"))
    assert r.priority in ("P1", "P2")


def test_confidence_is_not_saturated(agent):
    r = agent.triage(t("Printer is out of toner"))
    assert 0.35 <= r.confidence < 1.0


def test_runbook_parser_handles_windows_line_endings():
    text = (ROOT / "runbooks" / "printer.md").read_text(encoding="utf-8").replace("\n", "\r\n")
    book = parse_runbook(text)
    assert book.category == "printer"
    assert book.steps
