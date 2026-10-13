"""Cost control: estimate before sending, cache a long prefix, compare effort levels.

Prices are USD per million tokens for claude-opus-5-5 (check the pricing page, they change).
"""

import anthropic
from dotenv import load_dotenv

load_dotenv()
client = anthropic.Anthropic()
MODEL = "claude-opus-5-5"
PRICE_IN, PRICE_OUT, PRICE_CACHE_READ = 4.00, 20.00, 0.20

# A long, stable prefix (policies, docs, few-shot examples) is what caching is for.
POLICY = "\n".join(f"Rule {i}: refunds over ${i * 10} need manager approval and a ticket reference." for i in range(1, 400))


def cost(usage) -> float:
    return (
        usage.input_tokens * PRICE_IN
        + (usage.cache_creation_input_tokens or 0) * PRICE_IN * 1.25
        + (usage.cache_read_input_tokens or 0) * PRICE_CACHE_READ
        + usage.output_tokens * PRICE_OUT
    ) / 1_000_000


system = [{"type": "text", "text": POLICY, "cache_control": {"type": "ephemeral"}}]
estimate = client.messages.count_tokens(model=MODEL, system=system, messages=[{"role": "user", "content": "x"}])
print(f"Prefix size: ~{estimate.input_tokens} tokens")

for i, question in enumerate(["Does a $250 refund need approval?", "And a $5 refund?"], 1):
    r = client.messages.create(
        model=MODEL,
        max_tokens=512,
        system=system,
        output_config={"effort": "low"},
        messages=[{"role": "user", "content": question}],
    )
    u = r.usage
    print(
        f"call {i}: cache_write={u.cache_creation_input_tokens} cache_read={u.cache_read_input_tokens} "
        f"uncached_in={u.input_tokens} out={u.output_tokens} cost=${cost(u):.5f}"
    )

print("\nSame question, different effort:")
for effort in ("low", "high"):
    r = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        output_config={"effort": effort},
        messages=[{"role": "user", "content": "Is 2^31 - 1 prime? Answer yes or no and one line of reasoning."}],
    )
    print(f"  effort={effort:<5} output_tokens={r.usage.output_tokens} cost=${cost(r.usage):.5f}")
