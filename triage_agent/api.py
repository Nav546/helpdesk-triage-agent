from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from .agent import Ticket, TriageAgent

app = FastAPI(title="Helpdesk Triage Agent")
agent = TriageAgent()


class TicketIn(BaseModel):
    id: str = "TKT-1"
    summary: str
    description: str = ""
    use_llm: bool = False


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/triage")
def triage(body: TicketIn) -> dict:
    return agent.triage(Ticket(body.id, body.summary, body.description), use_llm=body.use_llm).to_dict()
