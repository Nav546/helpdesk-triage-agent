from __future__ import annotations

import argparse
import json
import sys

from .agent import Ticket, TriageAgent, draft_kb_article


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="triage", description="Read-only IT helpdesk triage agent")
    sub = p.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("ticket", help="triage one ticket")
    t.add_argument("summary")
    t.add_argument("--description", default="")
    t.add_argument("--id", default="TKT-1")
    t.add_argument("--llm", action="store_true", help="polish the reply with an LLM (needs ANTHROPIC_API_KEY)")

    f = sub.add_parser("file", help="triage a JSON file of tickets")
    f.add_argument("path")

    k = sub.add_parser("kb", help="draft a knowledge article from a solved ticket")
    k.add_argument("title")
    k.add_argument("--symptoms", required=True)
    k.add_argument("--step", action="append", required=True, help="repeat for each step")
    k.add_argument("--category", default="general")

    args = p.parse_args(argv)
    agent = TriageAgent()

    if args.cmd == "ticket":
        res = agent.triage(Ticket(args.id, args.summary, args.description), use_llm=args.llm)
        print(json.dumps(res.to_dict(), indent=2))
    elif args.cmd == "file":
        with open(args.path, encoding="utf-8") as fh:
            tickets = [Ticket(**d) for d in json.load(fh)]
        for tk in tickets:
            r = agent.triage(tk)
            flag = "ESCALATE" if r.escalate else "handle"
            print(f"{r.ticket_id:8} {r.priority}  {r.category:20} conf={r.confidence:.2f}  {flag}")
    elif args.cmd == "kb":
        print(draft_kb_article(args.title, args.symptoms, args.step, args.category))
    return 0


if __name__ == "__main__":
    sys.exit(main())
