"""Anthropic SDK essentials: client, system prompt, multi-turn, typed errors."""

import anthropic
from dotenv import load_dotenv

load_dotenv()
client = anthropic.Anthropic(max_retries=3, timeout=60.0)  # retries 408/409/429/5xx with backoff
MODEL = "claude-opus-5-5"
SYSTEM = "You are a concise assistant for a backend engineer. Answer in at most two sentences."

history: list[dict] = []


def send(text: str) -> str:
    history.append({"role": "user", "content": text})
    try:
        response = client.messages.create(model=MODEL, max_tokens=1024, system=SYSTEM, messages=history)
    except anthropic.RateLimitError as e:
        raise SystemExit(f"Rate limited, retry after {e.response.headers.get('retry-after')}s")
    except anthropic.APIStatusError as e:
        raise SystemExit(f"API error {e.status_code}: {e.message}")
    except anthropic.APIConnectionError:
        raise SystemExit("Network error")
    # Append the full content, not only the text: thinking blocks must travel back unchanged.
    history.append({"role": "assistant", "content": response.content})
    print(f"  [request_id={response._request_id} stop={response.stop_reason}]")
    return next(b.text for b in response.content if b.type == "text")


print("user> My service is called 'ledger-api' and it is written in Go.")
print("assistant>", send("My service is called 'ledger-api' and it is written in Go."))
print("user> What language is my service written in?")
print("assistant>", send("What language is my service written in?"))
print(f"\nThe API is stateless: we sent {len(history) - 1} messages in the last request.")
