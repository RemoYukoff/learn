"""Tiny in-memory CRM shared by every example in this module.

Plain Python on purpose: each framework wraps these functions with its own
tool decorator, so the business logic is identical across tabs.
"""

from __future__ import annotations

import json

CUSTOMERS = {
    "C-001": {"id": "C-001", "name": "Acme SA", "plan": "enterprise", "country": "AR"},
    "C-002": {"id": "C-002", "name": "Globex SRL", "plan": "starter", "country": "UY"},
}

TICKETS = {
    "T-100": {"id": "T-100", "customer_id": "C-001", "subject": "Invoice shows wrong VAT", "status": "open"},
    "T-101": {"id": "T-101", "customer_id": "C-001", "subject": "SSO login fails for new users", "status": "open"},
    "T-102": {"id": "T-102", "customer_id": "C-002", "subject": "Export to CSV is slow", "status": "closed"},
}

VALID_STATUSES = {"open", "pending", "closed"}


def get_customer(customer_id: str) -> str:
    """Return a customer record as JSON, or an error message."""
    customer = CUSTOMERS.get(customer_id)
    if customer is None:
        return f"Error: customer {customer_id} not found. Known ids: {sorted(CUSTOMERS)}"
    return json.dumps(customer)


def list_open_tickets(customer_id: str) -> str:
    """Return the open tickets of a customer as JSON."""
    tickets = [t for t in TICKETS.values() if t["customer_id"] == customer_id and t["status"] == "open"]
    return json.dumps(tickets)


def update_ticket_status(ticket_id: str, status: str) -> str:
    """Change a ticket status. This is the sensitive action in the HITL examples."""
    if ticket_id not in TICKETS:
        return f"Error: ticket {ticket_id} not found."
    if status not in VALID_STATUSES:
        return f"Error: status must be one of {sorted(VALID_STATUSES)}."
    TICKETS[ticket_id]["status"] = status
    return f"Ticket {ticket_id} is now {status}."
