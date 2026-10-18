"""Load runbooks from markdown files.

Format of each runbook file:

    ---
    title: ...
    category: ...
    keywords: a, b, c
    verify_identity: true|false
    always_escalate: true|false
    ---
    ## Steps
    1. ...
    ## Escalate when
    - ...
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Runbook:
    title: str
    category: str
    keywords: list[str]
    verify_identity: bool = False
    always_escalate: bool = False
    steps: list[str] = field(default_factory=list)
    escalate_when: list[str] = field(default_factory=list)


def _parse_list(block: str) -> list[str]:
    items = []
    for line in block.splitlines():
        line = line.strip()
        m = re.match(r"^(?:\d+\.|-)\s+(.*)$", line)
        if m:
            items.append(m.group(1).strip())
    return items


def parse_runbook(text: str) -> Runbook:
    text = text.replace("\r\n", "\n")  # Windows checkouts use CRLF
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        raise ValueError("runbook is missing front matter")
    meta: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    body = m.group(2)
    sections = re.split(r"^## ", body, flags=re.M)
    steps: list[str] = []
    escalate: list[str] = []
    for sec in sections:
        head, _, rest = sec.partition("\n")
        if head.strip().lower() == "steps":
            steps = _parse_list(rest)
        elif head.strip().lower().startswith("escalate"):
            escalate = _parse_list(rest)
    return Runbook(
        title=meta["title"],
        category=meta["category"],
        keywords=[k.strip().lower() for k in meta.get("keywords", "").split(",") if k.strip()],
        verify_identity=meta.get("verify_identity", "false").lower() == "true",
        always_escalate=meta.get("always_escalate", "false").lower() == "true",
        steps=steps,
        escalate_when=escalate,
    )


def load_runbooks(folder: str | Path) -> list[Runbook]:
    books = []
    for path in sorted(Path(folder).glob("*.md")):
        books.append(parse_runbook(path.read_text(encoding="utf-8")))
    if not books:
        raise FileNotFoundError(f"no runbooks found in {folder}")
    return books