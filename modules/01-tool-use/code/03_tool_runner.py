"""The same agent with the SDK's tool runner (beta): no hand-written loop.

@beta_tool builds the JSON Schema from type hints and the docstring's Args section.
"""

import anthropic
from anthropic import beta_tool
from dotenv import load_dotenv

import crm

load_dotenv()
client = anthropic.Anthropic()


@beta_tool
def find_customer(name: str) -> str:
    """Search customers by (partial) company name. Returns id, name, plan and email as JSON.

    Args:
        name: Company name or part of it.
    """
    return crm.find_customer(name)


@beta_tool
def list_tickets(customer_id: str, status: str = "open") -> str:
    """List support tickets of a customer filtered by status ("open" or "closed").

    Args:
        customer_id: Customer id like C-100.
        status: "open" or "closed".
    """
    return crm.list_tickets(customer_id, status)


@beta_tool
def update_ticket_status(ticket_id: str, status: str) -> str:
    """Change the status of a ticket ("open" or "closed"). Returns the updated ticket.

    Args:
        ticket_id: Ticket id like T-1.
        status: "open" or "closed".
    """
    return crm.update_ticket_status(ticket_id, status)


print("Schema generated for list_tickets:", list_tickets.to_dict()["input_schema"])

runner = client.beta.messages.tool_runner(
    model="claude-opus-5-5",
    max_tokens=8192,
    max_iterations=10,
    system="You are a support operations agent. Use the tools to answer. Be brief.",
    tools=[find_customer, list_tickets, update_ticket_status],
    messages=[{"role": "user", "content": "Acme says the CSV export is fixed. Close that ticket and tell me what is still open."}],
)

for message in runner:  # one iteration per model response
    for block in message.content:
        if block.type == "tool_use":
            print(f"-> {block.name}({block.input})")
        elif block.type == "text":
            print(block.text)
