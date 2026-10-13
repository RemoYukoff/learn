"""Short-term memory (checkpointer + thread_id) and long-term memory (store) in LangGraph.

Run: python 05_memory_langgraph.py   (needs ANTHROPIC_API_KEY in .env)

- Thread memory lives in memory.sqlite (SqliteSaver). Run the script twice:
  the second run continues the same conversation.
- User preferences live in a store namespace ("users", user_id) and are visible
  from any thread of that user.
"""

from __future__ import annotations

from dataclasses import dataclass

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.runtime import Runtime
from langgraph.store.memory import InMemoryStore

load_dotenv()

model = ChatAnthropic(model="claude-opus-5-5", max_tokens=2048)


@dataclass
class Context:
    user_id: str  # passed per run, not stored in the checkpoint


def chat(state: MessagesState, runtime: Runtime[Context]) -> dict:
    namespace = ("users", runtime.context.user_id)
    prefs = [item.value["text"] for item in runtime.store.search(namespace)]
    system = "You are a support assistant. Known user preferences: " + ("; ".join(prefs) or "none")

    last = state["messages"][-1].text
    if last.lower().startswith("remember:"):
        # Naive long-term write. Real systems let the model decide via a tool.
        runtime.store.put(namespace, f"pref-{len(prefs)}", {"text": last.split(":", 1)[1].strip()})

    reply = model.invoke([{"role": "system", "content": system}, *state["messages"]])
    return {"messages": [reply]}


builder = StateGraph(MessagesState, context_schema=Context)
builder.add_node("chat", chat)
builder.add_edge(START, "chat")

store = InMemoryStore()  # use PostgresStore / a DB-backed store in production


def ask(graph, thread_id: str, text: str) -> None:
    config = {"configurable": {"thread_id": thread_id}}
    result = graph.invoke({"messages": [("user", text)]}, config, context=Context(user_id="alice"))
    print(f"[{thread_id}] user: {text}\n[{thread_id}] bot:  {result['messages'][-1].text[:300]}\n")


if __name__ == "__main__":
    with SqliteSaver.from_conn_string("memory.sqlite") as checkpointer:
        graph = builder.compile(checkpointer=checkpointer, store=store)

        ask(graph, "ticket-1", "Remember: I prefer answers in Spanish.")
        ask(graph, "ticket-1", "My customer id is C-001. What did I just tell you my id was?")
        # New thread: no message history, but the store still has the preference.
        ask(graph, "ticket-2", "What is my customer id? And in which language should you answer?")

        snapshot = graph.get_state({"configurable": {"thread_id": "ticket-1"}})
        print(f"ticket-1 has {len(snapshot.values['messages'])} messages checkpointed in memory.sqlite")
