"""Human-in-the-loop in CrewAI: a Flow step decorated with @human_feedback routes on the answer.

Run (crewai venv): python 06_hitl_crewai.py   (needs ANTHROPIC_API_KEY, asks you in the terminal)

The human answers in free text; the `llm` collapses it to one of the `emit`
outcomes, and @listen(<outcome>) picks the next step.
"""

from __future__ import annotations

from crewai import LLM
from crewai.flow import Flow, human_feedback, listen, start
from dotenv import load_dotenv

import crm

load_dotenv()

llm = LLM(model="anthropic/claude-opus-5-5", max_tokens=1024)


class CloseTicketFlow(Flow):
    @start()
    @human_feedback(
        message="The agent wants to run this action. Approve or reject?",
        emit=["approved", "rejected"],
        llm=llm,
        default_outcome="rejected",
    )
    def propose(self):
        # In a real flow this proposal comes from a Crew or an Agent.
        return {"action": "update_ticket_status", "ticket_id": "T-100", "status": "closed"}

    @listen("approved")
    def execute(self):
        proposal = self.human_feedback.output
        print(crm.update_ticket_status(proposal["ticket_id"], proposal["status"]))

    @listen("rejected")
    def skip(self):
        print(f"Skipped. Human said: {self.human_feedback.feedback!r}")


if __name__ == "__main__":
    CloseTicketFlow().kickoff()
    print("Tickets now:", {t: v["status"] for t, v in crm.TICKETS.items()})
