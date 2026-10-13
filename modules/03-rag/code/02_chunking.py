"""Three chunking strategies on the same document, side by side.

1. Fixed size with overlap (characters)
2. Recursive: split on paragraphs, then lines, then sentences, then words
3. Structure-aware: split on Markdown headings and keep them as metadata

Then measures how each strategy affects retrieval on the labeled questions.
Runs offline.
"""

from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from rag_utils import Embedder, cosine_top_k, load_docs, load_questions

docs = load_docs()
text = docs["refunds.md"]


def fixed_size(t: str, size: int = 300, overlap: int = 50) -> list[str]:
    step = size - overlap
    return [t[i : i + size] for i in range(0, len(t), step)]


recursive = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=50)
by_heading = MarkdownHeaderTextSplitter(headers_to_split_on=[("#", "title"), ("##", "section")])

strategies = {
    "fixed": lambda t: fixed_size(t),
    "recursive": lambda t: recursive.split_text(t),
    "markdown": lambda t: [f"{d.metadata.get('title', '')} > {d.metadata.get('section', '')}\n{d.page_content}" for d in by_heading.split_text(t)],
}

for name, split in strategies.items():
    pieces = split(text)
    print(f"\n=== {name}: {len(pieces)} chunks ===")
    for p in pieces[:3]:
        print("  |", p.replace("\n", " ")[:110])

print("\n=== retrieval: does a top-k chunk contain the evidence sentence? ===")
embedder = Embedder()
questions = load_questions()
for name, split in strategies.items():
    chunks = [(doc, piece) for doc, t in docs.items() for piece in split(t)]
    matrix = embedder.passages([p for _, p in chunks])
    hit1 = hit3 = 0
    for q in questions:
        top = cosine_top_k(embedder.query(q["question"]), matrix, k=3)
        found = [q["evidence"] in chunks[i][1] for i, _ in top]
        hit1 += found[0]
        hit3 += any(found)
    n = len(questions)
    print(f"  {name:<10} chunks={len(chunks):<4} hit@1={hit1}/{n}  hit@3={hit3}/{n}")
