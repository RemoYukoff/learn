"""LangGraph streaming, subgraphs, Send (map-reduce) and time travel. No API key needed.

Run: python 08_streaming_subgraphs.py
"""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

import crm


# ---------- subgraph: summarizes ONE ticket (its own state schema) ----------
class TicketState(TypedDict):
    ticket_id: str
    summaries: Annotated[list[str], operator.add]  # same key as the parent -> merged upward


def summarize(state: TicketState) -> dict:
    writer = get_stream_writer()  # stream_mode="custom" receives whatever you write here
    writer({"progress": f"summarizing {state['ticket_id']}"})
    ticket = crm.TICKETS[state["ticket_id"]]
    return {"summaries": [f"{ticket['id']}: {ticket['subject']} ({ticket['status']})"]}


ticket_builder = StateGraph(TicketState)
ticket_builder.add_node("summarize", summarize)
ticket_builder.add_edge(START, "summarize")
ticket_graph = ticket_builder.compile()


# ---------- parent graph: fan out one subgraph run per ticket, then reduce ----------
class ReportState(TypedDict):
    customer_id: str
    ticket_ids: list[str]
    summaries: Annotated[list[str], operator.add]
    report: str


def load_tickets(state: ReportState) -> dict:
    ids = [t["id"] for t in crm.TICKETS.values() if t["customer_id"] == state["customer_id"]]
    return {"ticket_ids": ids}


def fan_out(state: ReportState) -> list[Send]:
    # Send(node, input): one parallel task per item, each with its own input.
    return [Send("ticket", {"ticket_id": tid, "summaries": []}) for tid in state["ticket_ids"]]


def write_report(state: ReportState) -> dict:
    lines = "\n".join(f"  - {s}" for s in sorted(state["summaries"]))
    return {"report": f"Customer {state['customer_id']}:\n{lines}"}


builder = StateGraph(ReportState)
builder.add_node("load_tickets", load_tickets)
builder.add_node("ticket", ticket_graph)  # a compiled graph is a valid node
builder.add_node("write_report", write_report)
builder.add_edge(START, "load_tickets")
builder.add_conditional_edges("load_tickets", fan_out, ["ticket"])
builder.add_edge("ticket", "write_report")  # waits for every Send branch
builder.add_edge("write_report", END)
graph = builder.compile(checkpointer=InMemorySaver())


def section(title: str) -> None:
    print(f"\n=== {title}")


if __name__ == "__main__":
    inputs = {"customer_id": "C-001", "ticket_ids": [], "summaries": [], "report": ""}

    section('stream_mode="updates": what each node returned')
    for chunk in graph.stream(inputs, {"configurable": {"thread_id": "u"}}, stream_mode="updates"):
        print(chunk)

    section('stream_mode="values": full state after each step (last 2 shown)')
    values = list(graph.stream(inputs, {"configurable": {"thread_id": "v"}}, stream_mode="values"))
    for state in values[-2:]:
        print({k: v for k, v in state.items() if k != "report"})

    section('stream_mode=["custom", "updates"] + subgraphs=True: namespaced events')
    for namespace, mode, data in graph.stream(
        inputs, {"configurable": {"thread_id": "c"}}, stream_mode=["custom", "updates"], subgraphs=True
    ):
        print(namespace or "(root)", mode, data)

    section("final report")
    config = {"configurable": {"thread_id": "t"}}
    print(graph.invoke(inputs, config)["report"])

    section("time travel: checkpoints of thread t, newest first")
    history = list(graph.get_state_history(config))
    for snap in history:
        print(f"  next={snap.next!s:<22} summaries={len(snap.values.get('summaries', []))}")

    # Re-run from the checkpoint taken right after load_tickets, with edited state.
    after_load = next(s for s in history if s.next == ("ticket", "ticket"))
    # update_state writes a NEW checkpoint (a fork) as if load_tickets had returned this
    # value, so the routing (fan_out) runs again with the edited ids. Older checkpoints stay.
    forked = graph.update_state(after_load.config, {"ticket_ids": ["T-100"]})
    section("fork: resumed from an earlier checkpoint with ticket_ids edited")
    replay = graph.invoke(None, forked)  # input None = continue from that checkpoint
    print(replay["report"])
