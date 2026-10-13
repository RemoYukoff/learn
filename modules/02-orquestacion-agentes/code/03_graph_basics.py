"""LangGraph mechanics without an LLM: state, reducers, nodes, edges, routing, loops.

Run: python 03_graph_basics.py   (no API key needed)

The "LLM" here is a keyword classifier so you can watch the graph itself.
"""

from __future__ import annotations

import operator
from typing import Annotated, Literal, TypedDict

from langgraph.graph import END, START, StateGraph


class TriageState(TypedDict):
    ticket: str  # input, overwritten on update (default reducer = replace)
    category: str
    draft: str
    attempts: int
    # Reducer: every node's returned list is appended instead of replacing it.
    log: Annotated[list[str], operator.add]


def classify(state: TriageState) -> dict:
    text = state["ticket"].lower()
    category = "billing" if any(w in text for w in ("invoice", "vat", "charge")) else "technical"
    return {"category": category, "log": [f"classify -> {category}"]}


def billing(state: TriageState) -> dict:
    return {"draft": "Billing team: we will reissue the invoice.", "log": ["billing drafted reply"]}


def technical(state: TriageState) -> dict:
    attempts = state.get("attempts", 0) + 1
    # First attempt is deliberately too short so the review loop runs once.
    draft = "Check SSO." if attempts == 1 else "Tech team: we reset your SSO metadata, please retry login."
    return {"draft": draft, "attempts": attempts, "log": [f"technical attempt {attempts}"]}


def review(state: TriageState) -> dict:
    return {"log": [f"review draft ({len(state['draft'])} chars)"]}


# Routing functions return the name of the next node (or END).
def route_by_category(state: TriageState) -> Literal["billing", "technical"]:
    return state["category"]


def route_after_review(state: TriageState) -> Literal["technical", "__end__"]:
    too_short = len(state["draft"]) < 20
    if state["category"] == "technical" and too_short and state["attempts"] < 3:
        return "technical"  # loop back: graphs can have cycles, chains cannot
    return END


builder = StateGraph(TriageState)
builder.add_node("classify", classify)
builder.add_node("billing", billing)
builder.add_node("technical", technical)
builder.add_node("review", review)

builder.add_edge(START, "classify")
builder.add_conditional_edges("classify", route_by_category)
builder.add_edge("billing", "review")
builder.add_edge("technical", "review")
builder.add_conditional_edges("review", route_after_review)

graph = builder.compile()

if __name__ == "__main__":
    print("Graph structure (Mermaid):\n")
    print(graph.get_graph().draw_mermaid())

    for ticket in ("My invoice shows wrong VAT", "SSO login fails for new users"):
        print(f"\n=== Ticket: {ticket!r}")
        final = graph.invoke({"ticket": ticket, "attempts": 0, "log": []})
        for line in final["log"]:
            print("  ", line)
        print("   final draft:", final["draft"])
