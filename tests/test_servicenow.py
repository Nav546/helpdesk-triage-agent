import json

import pytest

from triage_agent import TriageAgent
from triage_agent.servicenow import ServiceNowClient, ServiceNowError, format_work_note, triage_incidents

INCIDENTS = {
    "result": [
        {"sys_id": "a1", "number": "INC0010001", "short_description": "Locked out of my account", "description": "Too many attempts, urgent"},
        {"sys_id": "b2", "number": "INC0010002", "short_description": "Suspicious email", "description": "I clicked a phishing link"},
    ]
}


class FakeSN:
    def __init__(self):
        self.calls = []

    def __call__(self, method, url, headers, body):
        self.calls.append((method, url, headers, body))
        if method == "GET":
            return 200, json.dumps(INCIDENTS)
        return 200, "{}"


def client(fake):
    return ServiceNowClient("https://dev12345.service-now.com", "admin", "pw", transport=fake)


def test_dry_run_reads_but_never_writes():
    fake = FakeSN()
    rows = triage_incidents(client(fake), TriageAgent(), apply=False)
    assert [c[0] for c in fake.calls] == ["GET"]
    assert all(r["written"] is False for r in rows)
    assert rows[0]["category"] == "account_lockout"
    assert rows[1]["escalate"] is True


def test_apply_writes_only_work_notes():
    fake = FakeSN()
    triage_incidents(client(fake), TriageAgent(), apply=True)
    patches = [c for c in fake.calls if c[0] == "PATCH"]
    assert len(patches) == 2
    for _, url, _, body in patches:
        assert "/api/now/table/incident/" in url
        payload = json.loads(body)
        assert list(payload.keys()) == ["work_notes"]


def test_https_required():
    with pytest.raises(ValueError):
        ServiceNowClient("http://dev12345.service-now.com", "u", "p")


def test_from_env_requires_variables(monkeypatch):
    for v in ("SN_INSTANCE", "SN_USER", "SN_PASSWORD"):
        monkeypatch.delenv(v, raising=False)
    with pytest.raises(ServiceNowError):
        ServiceNowClient.from_env()


def test_http_error_raises_without_leaking_credentials():
    def bad(method, url, headers, body):
        return 401, "unauthorized"

    c = ServiceNowClient("https://dev1.service-now.com", "admin", "secret-pw", transport=bad)
    with pytest.raises(ServiceNowError) as e:
        c.list_new_incidents()
    assert "secret-pw" not in str(e.value)


def test_work_note_contains_review_warning_and_steps():
    r = TriageAgent().triage(__import__("triage_agent").Ticket("T1", "Forgot my password", "expired"))
    note = format_work_note(r)
    assert "review before acting" in note
    assert "Identity verification required: yes" in note
    assert "1." in note
