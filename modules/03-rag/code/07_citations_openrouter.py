"""Grounded answers with citations through OpenRouter (any model).

Without a native citations feature, you number the sources in the prompt and
ask for structured output that lists the source ids behind each claim. Then you
validate the ids in code: a citation to a source you did not send is a red flag.
"""

import os
import sys

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field

from rag_utils import Embedder, all_chunks, cosine_top_k

load_dotenv()
QUESTION = sys.argv[1] if len(sys.argv) > 1 else "Our CFO wants money back for a 3,500 USD charge. Who signs off, and could they get credits instead?"


class Claim(BaseModel):
    text: str
    source_ids: list[str] = Field(description="ids of the sources that support this sentence")


class GroundedAnswer(BaseModel):
    claims: list[Claim]
    missing_information: str | None = Field(description="what the sources do not cover, if anything")


chunks = all_chunks()
embedder = Embedder()
hits = cosine_top_k(embedder.query(QUESTION), embedder.passages([c.text for c in chunks]), k=4)
sources = {chunks[i].id: chunks[i].text for i, _ in hits}
print(f"Retrieved: {list(sources)}")
if not os.environ.get("OPENROUTER_API_KEY"):
    sys.exit("OPENROUTER_API_KEY not set: skipping generation.")

context = "\n\n".join(f'<source id="{sid}">\n{text}\n</source>' for sid, text in sources.items())
client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.environ["OPENROUTER_API_KEY"])
completion = client.chat.completions.parse(
    model=os.environ.get("OPENROUTER_MODEL", "anthropic/claude-opus-5.5"),
    max_tokens=2048,
    messages=[
        {"role": "system", "content": "Answer only from the sources. Every claim must cite the ids of the sources that support it."},
        {"role": "user", "content": f"{context}\n\nQuestion: {QUESTION}"},
    ],
    response_format=GroundedAnswer,
)
answer = completion.choices[0].message.parsed
print(f"\nQuestion: {QUESTION}\n")
for claim in answer.claims:
    unknown = [s for s in claim.source_ids if s not in sources]
    flag = f"  <- unknown source {unknown}" if unknown else ""
    print(f"- {claim.text} {claim.source_ids}{flag}")
if answer.missing_information:
    print(f"\nMissing: {answer.missing_information}")
