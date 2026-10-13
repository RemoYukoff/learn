"""A tiny in-memory CRM that every example in this module operates on.

Plain Python functions plus their JSON Schemas. Swap the bodies for real HTTP calls
(HubSpot, Salesforce, your own API) and nothing else in the agent changes.
"""

from __future__ import annotations

import json

CUSTOMERS = {
    "C-100": {"id": "C-100", "name": "Acme Corp", "plan": "enterprise", "email": "ops@acme.example"},
    "C-200": {"id": "C-200", "name": "Globex", "plan": "starter", "email": "it@globex.example"},
}

TICKETS = {
    "T-1": {"id": "T-1", "customer_id": "C-100", "subject": "Double charge in October", "status": "open"},
    "T-2": {"id": "T-2", "customer_id": "C-100", "subject": "Export to CSV broken", "status": "open"},
    "T-3": {"id": "T-3", "customer_id": "C-200", "subject": "Add SSO", "status": "closed"},
}

REFUNDS: list[dict] = []


def find_customer(name: str) -> str:
    matches = [c for c in CUSTOMERS.values() if name.lower() in c["name"].lower()]
    if not matches:
        raise LookupError(f"No customer matches '{name}'. Known customers: {[c['name'] for c in CUSTOMERS.values()]}")
    return json.dumps(matches)


def list_tickets(customer_id: str, status: str = "open") -> str:
    if customer_id not in CUSTOMERS:
        raise LookupError(f"Unknown customer_id '{customer_id}'. Use find_customer first.")
    return json.dumps([t for t in TICKETS.values() if t["customer_id"] == customer_id and t["status"] == status])


def update_ticket_status(ticket_id: str, status: str) -> str:
    if ticket_id not in TICKETS:
        raise LookupError(f"Unknown ticket_id '{ticket_id}'")
    TICKETS[ticket_id]["status"] = status
    return json.dumps(TICKETS[ticket_id])


def issue_refund(customer_id: str, amount_usd: float, reason: str) -> str:
    if customer_id not in CUSTOMERS:
        raise LookupError(f"Unknown customer_id '{customer_id}'")
    refund = {"id": f"R-{len(REFUNDS) + 1}", "customer_id": customer_id, "amount_usd": amount_usd, "reason": reason}
    REFUNDS.append(refund)
    return json.dumps(refund)


# Tool definitions in Anthropic format: name, description, input_schema (JSON Schema).
# The description is a prompt: say what the tool does, when to use it, and what it returns.
TOOLS = [
    {
        "name": "find_customer",
        "description": "Search customers by (partial) company name. Returns a JSON list with id, name, plan and email. "
        "Use it to get the customer_id that the other tools need.",
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "Company name or part of it"}},
            "required": ["name"],
            "additionalProperties": False,
        },
    },
    {
        "name": "list_tickets",
        "description": "List support tickets of a customer filtered by status. Returns a JSON list.",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string", "description": "Customer id like C-100"},
                "status": {"type": "string", "enum": ["open", "closed"]},
            },
            "required": ["customer_id", "status"],
            "additionalProperties": False,
        },
    },
    {
        "name": "update_ticket_status",
        "description": "Change the status of a ticket. Returns the updated ticket.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string", "description": "Ticket id like T-1"},
                "status": {"type": "string", "enum": ["open", "closed"]},
            },
            "required": ["ticket_id", "status"],
            "additionalProperties": False,
        },
    },
    {
        "name": "issue_refund",
        "description": "Refund money to a customer. Irreversible. Only use when the user explicitly asks for a refund.",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "amount_usd": {"type": "number", "description": "Positive amount in USD"},
                "reason": {"type": "string", "description": "Short reason, references the ticket id"},
            },
            "required": ["customer_id", "amount_usd", "reason"],
            "additionalProperties": False,
        },
    },
]

FUNCTIONS = {
    "find_customer": find_customer,
    "list_tickets": list_tickets,
    "update_ticket_status": update_ticket_status,
    "issue_refund": issue_refund,
}


def to_openai(tools: list[dict]) -> list[dict]:
    """Same tools in OpenAI / OpenRouter Chat Completions format."""
    return [
        {
            "type": "function",
            "function": {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]},
        }
        for t in tools
    ]
