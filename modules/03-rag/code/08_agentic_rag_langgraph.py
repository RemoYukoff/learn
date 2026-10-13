"""Corrective RAG as a LangGraph graph.

retrieve -> grade the chunks -> enough? -> generate
                              -> not enough -> rewrite the query -> retrieve (max 2 rewrites)

The LLM grades relevance and rewrites queries; the graph decides the flow.
Needs ANTHROPIC_API_KEY.
"""

import operator
import sys
from typing import Annotated, Literal, TypedDict

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from rag_utils import HybridRetriever

load_dotenv()
retriever = HybridRetriever()
llm = ChatAnthropic(model="claude-opus-5-5", max_tokens=2048)
MAX_REWRITES = 2


class State(TypedDict):
    question: str
    query: str
    chunks: list[str]
    rewrites: int
    log: Annotated[list[str], operator.add]
    answer: str


class Relevance(BaseModel):
    relevant_ids: list[int] = Field(description="indexes of the chunks that help answer the question")
    enough: bool = Field(description="true if the relevant chunks fully answer the question")


class Rewrite(BaseModel):
    query: str = Field(description="a better search query for a company handbook")


# method="json_schema" uses native structured outputs. The default (forced tool calling)
# is rejected by claude-opus-5-5.
grader = llm.with_structured_output(Relevance, method="json_schema")
rewriter = llm.with_structured_output(Rewrite, method="json_schema")


def retrieve(state: State) -> dict:
    chunks = [c.text for c in retriever.search(state["query"], top=4)]
    return {"chunks": chunks, "log": [f"retrieve({state['query']!r})"]}


def grade(state: State) -> dict:
    numbered = "\n\n".join(f"[{i}] {c}" for i, c in enumerate(state["chunks"]))
    verdict = grader.invoke(f"Question: {state['question']}\n\nChunks:\n{numbered}")
    kept = [state["chunks"][i] for i in verdict.relevant_ids if i < len(state["chunks"])]
    return {"chunks": kept, "log": [f"grade: kept {len(kept)}, enough={verdict.enough}"], "answer": "" if verdict.enough else "NEED_MORE"}


def route(state: State) -> Literal["generate", "rewrite"]:
    if state["answer"] == "NEED_MORE" and state["rewrites"] < MAX_REWRITES:
        return "rewrite"
    return "generate"


def rewrite(state: State) -> dict:
    new = rewriter.invoke(f"The search query {state['query']!r} did not find enough to answer: {state['question']}").query
    return {"query": new, "rewrites": state["rewrites"] + 1, "log": [f"rewrite -> {new!r}"]}


def generate(state: State) -> dict:
    context = "\n\n".join(state["chunks"]) or "(no relevant context found)"
    msg = llm.invoke([
        ("system", "Answer from the context only. If it is not enough, say what is missing."),
        ("user", f"<context>\n{context}\n</context>\n\nQuestion: {state['question']}"),
    ])
    return {"answer": msg.text, "log": ["generate"]}


builder = StateGraph(State)
for name, fn in (("retrieve", retrieve), ("grade", grade), ("rewrite", rewrite), ("generate", generate)):
    builder.add_node(name, fn)
builder.add_edge(START, "retrieve")
builder.add_edge("retrieve", "grade")
builder.add_conditional_edges("grade", route)
builder.add_edge("rewrite", "retrieve")
builder.add_edge("generate", END)
graph = builder.compile()

question = sys.argv[1] if len(sys.argv) > 1 else "I was paged three nights this week during my rotation. What do I get on top of the stipend?"
result = graph.invoke({"question": question, "query": question, "chunks": [], "rewrites": 0, "log": [], "answer": ""})
print("\n".join(f"  {step}" for step in result["log"]))
print(f"\n{result['answer']}")
