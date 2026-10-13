"""Evaluate retrieval with labeled questions: hit@k, MRR and nDCG for four strategies.

Ground truth: each question in data/questions.json has an `evidence` sentence;
a chunk is relevant if it contains it. Runs offline.

With ANTHROPIC_API_KEY set, also generates answers from the best strategy and
grades them with an LLM judge (correctness and faithfulness to the context).
"""

import math
import os
import time
from typing import Literal

import bm25s
from dotenv import load_dotenv
from fastembed.rerank.cross_encoder import TextCrossEncoder
from pydantic import BaseModel

from rag_utils import Embedder, all_chunks, cosine_top_k, load_questions

load_dotenv()
K = 10
chunks = all_chunks()
texts = [c.text for c in chunks]
questions = load_questions()

embedder = Embedder()
matrix = embedder.passages(texts)
bm25 = bm25s.BM25()
bm25.index(bm25s.tokenize(texts, stopwords="en", show_progress=False), show_progress=False)
reranker = TextCrossEncoder("Xenova/ms-marco-MiniLM-L-6-v2")


def dense(q):
    return [i for i, _ in cosine_top_k(embedder.query(q), matrix, K)]


def sparse(q):
    ids, _ = bm25.retrieve(bm25s.tokenize([q], stopwords="en", show_progress=False), k=K, show_progress=False)
    return [int(i) for i in ids[0]]


def hybrid(q):
    scores = {}
    for ranking in (dense(q), sparse(q)):
        for rank, i in enumerate(ranking, 1):
            scores[i] = scores.get(i, 0) + 1 / (60 + rank)
    return sorted(scores, key=scores.get, reverse=True)[:K]


def hybrid_rerank(q):
    cands = hybrid(q)
    scores = list(reranker.rerank(q, [texts[i] for i in cands]))
    return [i for _, i in sorted(zip(scores, cands), reverse=True)]


def metrics(ranking: list[int], evidence: str) -> dict[str, float]:
    rel = [evidence in texts[i] for i in ranking]
    first = next((n for n, r in enumerate(rel, 1) if r), None)
    dcg = sum(1 / math.log2(n + 1) for n, r in enumerate(rel, 1) if r)
    return {
        "hit@1": float(first == 1),
        "hit@3": float(first is not None and first <= 3),
        "hit@10": float(first is not None),
        "mrr": 1 / first if first else 0.0,
        "ndcg@10": dcg,  # one relevant chunk per question, so the ideal DCG is 1
    }


strategies = {"dense": dense, "bm25": sparse, "hybrid": hybrid, "hybrid+rerank": hybrid_rerank}
print(f"{len(questions)} questions, {len(chunks)} chunks\n")
print(f"{'strategy':<14} {'hit@1':>6} {'hit@3':>6} {'hit@10':>7} {'MRR':>6} {'nDCG@10':>8} {'ms/query':>9}")
for name, fn in strategies.items():
    start = time.perf_counter()
    rows = [metrics(fn(q["question"]), q["evidence"]) for q in questions]
    ms = (time.perf_counter() - start) * 1000 / len(questions)
    avg = {k: sum(r[k] for r in rows) / len(rows) for k in rows[0]}
    print(f"{name:<14} {avg['hit@1']:>6.2f} {avg['hit@3']:>6.2f} {avg['hit@10']:>7.2f} {avg['mrr']:>6.2f} {avg['ndcg@10']:>8.2f} {ms:>9.1f}")

if not os.environ.get("ANTHROPIC_API_KEY"):
    raise SystemExit("\nANTHROPIC_API_KEY not set: skipping answer generation and LLM-as-judge.")

import anthropic  # noqa: E402

client = anthropic.Anthropic()


class Grade(BaseModel):
    correct: Literal["yes", "partial", "no"]
    faithful: bool  # every claim in the answer is supported by the context
    reason: str


print("\nGenerating answers with hybrid+rerank top 3 and grading them...")
tally = {"yes": 0, "partial": 0, "no": 0, "unfaithful": 0}
for q in questions:
    context = "\n\n".join(texts[i] for i in hybrid_rerank(q["question"])[:3])
    answer = client.messages.create(
        model="claude-opus-5-5", max_tokens=1024, output_config={"effort": "low"},
        system="Answer from the context only, in one or two sentences. If the context is not enough, say so.",
        messages=[{"role": "user", "content": f"<context>\n{context}\n</context>\n\nQuestion: {q['question']}"}],
    )
    answer_text = next(b.text for b in answer.content if b.type == "text")
    grade = client.messages.parse(
        model="claude-opus-5-5", max_tokens=1024, output_config={"effort": "low"},
        messages=[{"role": "user", "content": (
            f"<question>{q['question']}</question>\n<reference>{q['answer']}</reference>\n"
            f"<context>{context}</context>\n<answer>{answer_text}</answer>\n"
            "Grade the answer: is it correct compared to the reference, and is every claim supported by the context?"
        )}],
        output_format=Grade,
    ).parsed_output
    tally[grade.correct] += 1
    tally["unfaithful"] += not grade.faithful
    print(f"  {grade.correct:<7} faithful={grade.faithful!s:<5} {q['question'][:60]}")
print(f"\ncorrect={tally['yes']} partial={tally['partial']} wrong={tally['no']} unfaithful={tally['unfaithful']}")
