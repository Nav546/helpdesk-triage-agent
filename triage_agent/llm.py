"""Optional LLM polish step.

The agent is deterministic and works offline. If an API key is present and the
caller asks for it, the model only rewrites the reply draft. It is given the
runbook steps and nothing else, so it cannot invent procedures.
"""
from __future__ import annotations

import os

SYSTEM = (
    "You write short, friendly IT service desk replies. Use ONLY the steps you are "
    "given. Do not add new troubleshooting steps. Never ask for passwords or MFA "
    "codes. If identity verification is required, say it must be done first. "
    "Keep it under 120 words."
)


def polish_reply(draft: str, steps: list[str], verify_identity: bool) -> str:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return draft
    try:
        import anthropic  # lazy import, optional dependency
    except ImportError:
        return draft
    client = anthropic.Anthropic(api_key=key)
    prompt = (
        f"Draft reply:\n{draft}\n\nAllowed steps:\n"
        + "\n".join(f"- {s}" for s in steps)
        + f"\n\nIdentity verification required: {verify_identity}\n\nRewrite the draft."
    )
    msg = client.messages.create(
        model=os.environ.get("TRIAGE_MODEL", "claude-sonnet-5-5"),
        max_tokens=400,
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(b.text for b in msg.content if getattr(b, "text", None)).strip() or draft
