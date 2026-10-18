from __future__ import annotations

import re
from dataclasses import dataclass, asdict, field
from pathlib import Path

from .runbooks import Runbook, load_runbooks

DEFAULT_RUNBOOKS = Path(__file__).resolve().parent.parent / "runbooks"

P1_WORDS = ["all stores", "everyone", "outage", "down for", "cannot trade", "can't trade", "all users", "ransomware"]
P2_WORDS = ["cannot work", "can't work", "unable to work", "urgent", "blocked", "locked out", "no access"]
SECURITY_WORDS = ["phishing", "suspicious", "clicked a link", "compromised", "unknown login", "ransomware", "hacked"]


@dataclass
class Ticket:
    id: str
    summary: str
    description: str = ""

    @property
    def text(self) -> str:
        return f"{self.summary} {self.description}".lower()


@dataclass
class TriageResult:
    ticket_id: str
    category: str
    priority: str
    confidence: float
    runbook: str | None
    verify_identity: bool
    escalate: bool
    escalation_reason: str
    steps: list[str] = field(default_factory=list)
    reply_draft: str = ""
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9']+", text.lower()))


class TriageAgent:
    """Read-only triage agent.

    It classifies a ticket, picks a runbook and drafts a reply. It never performs
    account changes. Sensitive categories always carry an identity verification
    reminder, and security issues always escalate.
    """

    def __init__(self, runbooks: list[Runbook] | None = None, min_confidence: float = 0.35):
        self.runbooks = runbooks if runbooks is not None else load_runbooks(DEFAULT_RUNBOOKS)
        self.min_confidence = min_confidence

    def _score(self, ticket: Ticket, book: Runbook) -> float:
        text = ticket.text
        toks = _tokens(text)
        hits = 0.0
        for kw in book.keywords:
            if " " in kw:
                if kw in text:
                    hits += 1.5  # phrase match is stronger
            elif kw in toks:
                hits += 1.0
        return hits

    def classify(self, ticket: Ticket) -> tuple[Runbook | None, float]:
        scored = sorted(((self._score(ticket, b), b) for b in self.runbooks), key=lambda x: x[0], reverse=True)
        best_score, best = scored[0]
        if best_score == 0:
            return None, 0.0
        second = scored[1][0] if len(scored) > 1 else 0.0
        # share of the evidence that points at the winner; a close runner-up lowers it
        conf = best_score / (best_score + second + 1.5)
        return best, round(conf, 2)

    def priority(self, ticket: Ticket) -> str:
        text = ticket.text
        if any(w in text for w in P1_WORDS):
            return "P1"
        if any(w in text for w in P2_WORDS):
            return "P2"
        return "P3"

    def triage(self, ticket: Ticket, use_llm: bool = False) -> TriageResult:
        book, conf = self.classify(ticket)
        prio = self.priority(ticket)
        notes: list[str] = []
        is_security = any(w in ticket.text for w in SECURITY_WORDS)

        if book is None or conf < self.min_confidence:
            result = TriageResult(
                ticket_id=ticket.id,
                category="unclassified",
                priority=prio,
                confidence=conf,
                runbook=None,
                verify_identity=False,
                escalate=True,
                escalation_reason="Low confidence. A human should read this ticket.",
                reply_draft="Thanks for contacting IT. We have your request and an analyst will pick it up shortly.",
            )
            if is_security:
                result.category = "security_incident"
                result.priority = "P1" if prio == "P3" else prio
                result.escalation_reason = "Possible security issue. Escalate to the security team."
                result.notes.append("Security keywords found.")
            return result

        escalate = book.always_escalate or is_security
        reason = ""
        if book.always_escalate:
            reason = f"'{book.category}' is always escalated."
        if is_security and not book.always_escalate:
            reason = "Security keywords found. Escalate to the security team."
            prio = "P1" if prio == "P3" else prio
            notes.append("Security keywords found, so priority was raised.")
        if conf < 0.5 and not escalate:
            notes.append("Medium confidence. Check the category before sending the reply.")
        if book.category == "security_incident" and prio == "P3":
            prio = "P2"
        if prio == "P1":
            escalate = True
            reason = reason or "P1 impact. Escalate immediately."

        draft = self._draft_reply(ticket, book)
        if use_llm:
            from .llm import polish_reply

            draft = polish_reply(draft, book.steps, book.verify_identity)

        return TriageResult(
            ticket_id=ticket.id,
            category=book.category,
            priority=prio,
            confidence=conf,
            runbook=book.title,
            verify_identity=book.verify_identity,
            escalate=escalate,
            escalation_reason=reason,
            steps=book.steps,
            reply_draft=draft,
            notes=notes,
        )

    @staticmethod
    def _draft_reply(ticket: Ticket, book: Runbook) -> str:
        lines = ["Hi,", "", f"Thanks for raising this ({ticket.id})."]
        if book.verify_identity:
            lines.append(
                "Before we change anything on your account, we need to verify your identity. "
                "Please do not send us your password or any MFA codes."
            )
        lines.append("Here is what we will do next:")
        lines += [f"{i}. {s}" for i, s in enumerate(book.steps[:4], 1)]
        lines += ["", "We will keep you updated until this is resolved.", "IT Service Desk"]
        return "\n".join(lines)


def draft_kb_article(title: str, symptoms: str, resolution_steps: list[str], category: str = "general") -> str:
    """Turn a solved ticket into a knowledge article draft (markdown)."""
    steps = "\n".join(f"{i}. {s}" for i, s in enumerate(resolution_steps, 1))
    return (
        f"# {title}\n\n"
        f"**Category:** {category}\n\n"
        f"## Symptoms\n{symptoms}\n\n"
        f"## Resolution\n{steps}\n\n"
        "## Notes\n- Review before publishing. Remove names, hostnames and any customer data.\n"
    )
