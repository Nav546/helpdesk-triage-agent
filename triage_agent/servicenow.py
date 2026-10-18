"""Optional ServiceNow connector (Table API).

Safety design:
- Dry run by default. Nothing is written unless apply=True.
- When applying, the ONLY field written is `work_notes`. It never changes state,
  priority, assignment or category, and never resets accounts.
- HTTPS only. Credentials come from environment variables, never from files.
"""
from __future__ import annotations

import base64
import json
import os
import urllib.parse
import urllib.request
from typing import Callable

from .agent import Ticket, TriageAgent, TriageResult

# transport(method, url, headers, body_bytes_or_None) -> (status_code, response_text)
Transport = Callable[[str, str, dict, "bytes | None"], "tuple[int, str]"]

NOTE_HEADER = "[Triage agent suggestion - review before acting]"


def _urllib_transport(timeout: int = 15) -> Transport:
    def send(method: str, url: str, headers: dict, body: "bytes | None") -> "tuple[int, str]":
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (https enforced)
                return resp.status, resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", errors="replace")

    return send


class ServiceNowError(RuntimeError):
    pass


class ServiceNowClient:
    def __init__(self, instance_url: str, username: str, password: str, transport: "Transport | None" = None):
        if not instance_url.lower().startswith("https://"):
            raise ValueError("ServiceNow instance URL must start with https://")
        self.base = instance_url.rstrip("/")
        token = base64.b64encode(f"{username}:{password}".encode()).decode()
        self._headers = {
            "Authorization": f"Basic {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        self._send = transport or _urllib_transport()

    @classmethod
    def from_env(cls, transport: "Transport | None" = None) -> "ServiceNowClient":
        try:
            return cls(os.environ["SN_INSTANCE"], os.environ["SN_USER"], os.environ["SN_PASSWORD"], transport)
        except KeyError as e:
            raise ServiceNowError(f"Set the {e.args[0]} environment variable") from None

    def _call(self, method: str, path: str, params: "dict | None" = None, payload: "dict | None" = None) -> dict:
        url = f"{self.base}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        body = json.dumps(payload).encode() if payload is not None else None
        status, text = self._send(method, url, self._headers, body)
        if status >= 300:
            raise ServiceNowError(f"ServiceNow returned HTTP {status}")
        return json.loads(text) if text else {}

    def list_new_incidents(self, limit: int = 10) -> list[dict]:
        data = self._call(
            "GET",
            "/api/now/table/incident",
            params={
                "sysparm_query": "state=1^ORDERBYDESCsys_created_on",
                "sysparm_limit": str(limit),
                "sysparm_fields": "sys_id,number,short_description,description",
            },
        )
        return data.get("result", [])

    def add_work_note(self, sys_id: str, note: str) -> None:
        # Only work_notes is ever sent.
        self._call("PATCH", f"/api/now/table/incident/{sys_id}", payload={"work_notes": note})


def format_work_note(r: TriageResult) -> str:
    lines = [
        NOTE_HEADER,
        f"Suggested category: {r.category}",
        f"Suggested priority: {r.priority} (confidence {r.confidence:.2f})",
        f"Identity verification required: {'yes' if r.verify_identity else 'no'}",
    ]
    if r.escalate:
        lines.append(f"Escalate to a human: yes. {r.escalation_reason}")
    else:
        lines.append("Escalate to a human: no")
    if r.steps:
        lines.append("Suggested steps:")
        lines += [f"{i}. {s}" for i, s in enumerate(r.steps, 1)]
    for n in r.notes:
        lines.append(f"Note: {n}")
    return "\n".join(lines)


def triage_incidents(client: ServiceNowClient, agent: TriageAgent, limit: int = 10, apply: bool = False) -> list[dict]:
    out = []
    for inc in client.list_new_incidents(limit):
        ticket = Ticket(inc.get("number", inc.get("sys_id", "?")), inc.get("short_description", ""), inc.get("description", ""))
        result = agent.triage(ticket)
        note = format_work_note(result)
        if apply:
            client.add_work_note(inc["sys_id"], note)
        out.append({"number": ticket.id, "category": result.category, "priority": result.priority,
                    "escalate": result.escalate, "note": note, "written": apply})
    return out
