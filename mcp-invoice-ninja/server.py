"""
MCP Server for Invoice Ninja — ClientFlow AI
Provides tools for managing clients, invoices, quotes, payments
via the Invoice Ninja REST API.
"""

import os
import json
import httpx
from datetime import datetime
from fastmcp import FastMCP

# Configuration
NINJA_URL = os.environ.get("NINJA_URL", "https://invoice.millyweb.com")
NINJA_TOKEN = os.environ.get("NINJA_TOKEN", "")

transport = os.environ.get("MCP_TRANSPORT", "streamable-http")
port = int(os.environ.get("MCP_PORT", "8000"))

mcp = FastMCP(
    "invoice-ninja",
    host="0.0.0.0",
    port=port,
)

# --- HTTP Client ---

def get_headers():
    return {
        "X-Api-Token": NINJA_TOKEN,
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

async def api_get(endpoint: str, params: dict = None) -> dict:
    async with httpx.AsyncClient(verify=False, timeout=30) as client:
        resp = await client.get(f"{NINJA_URL}/api/v1/{endpoint}", headers=get_headers(), params=params)
        resp.raise_for_status()
        return resp.json()

async def api_post(endpoint: str, data: dict) -> dict:
    async with httpx.AsyncClient(verify=False, timeout=30) as client:
        resp = await client.post(f"{NINJA_URL}/api/v1/{endpoint}", headers=get_headers(), json=data)
        resp.raise_for_status()
        return resp.json()

async def api_put(endpoint: str, data: dict) -> dict:
    async with httpx.AsyncClient(verify=False, timeout=30) as client:
        resp = await client.put(f"{NINJA_URL}/api/v1/{endpoint}", headers=get_headers(), json=data)
        resp.raise_for_status()
        return resp.json()

async def api_delete(endpoint: str) -> dict:
    async with httpx.AsyncClient(verify=False, timeout=30) as client:
        resp = await client.delete(f"{NINJA_URL}/api/v1/{endpoint}", headers=get_headers())
        resp.raise_for_status()
        return resp.json()


# ============================================================
# CLIENT TOOLS
# ============================================================

@mcp.tool()
async def list_clients(search: str = "", per_page: int = 20, page: int = 1, status: str = "active") -> str:
    """List all clients, optionally filtered by search term.
    
    Args:
        search: Search by client name, email, or contact info
        per_page: Results per page (default 20)
        page: Page number
        status: Filter by status (active, archived, deleted)
    """
    params = {"per_page": per_page, "page": page, "status": status}
    if search:
        params["filter"] = search
    result = await api_get("clients", params)
    clients = result.get("data", [])
    if not clients:
        return "No clients found."
    lines = [f"Found {len(clients)} client(s):\n"]
    for c in clients:
        name = c.get("name") or c.get("display_name", "Unnamed")
        contacts = c.get("contacts", [])
        email = contacts[0].get("email", "") if contacts else ""
        balance = c.get("balance", 0)
        paid = c.get("paid_to_date", 0)
        lines.append(f"- **{name}** (ID: {c['id']})\n  Email: {email} | Balance: ${balance:.2f} | Total Paid: ${paid:.2f}")
    return "\n".join(lines)


@mcp.tool()
async def get_client(client_id: str) -> str:
    """Get detailed information about a specific client.
    
    Args:
        client_id: The Invoice Ninja client ID
    """
    result = await api_get(f"clients/{client_id}")
    c = result.get("data", {})
    contacts = c.get("contacts", [])
    contact_lines = []
    for ct in contacts:
        contact_lines.append(f"  - {ct.get('first_name', '')} {ct.get('last_name', '')} <{ct.get('email', '')}> {ct.get('phone', '')}")
    return (
        f"**{c.get('name', 'Unnamed')}**\nID: {c['id']}\n"
        f"Balance: ${c.get('balance', 0):.2f}\nTotal Paid: ${c.get('paid_to_date', 0):.2f}\n"
        f"Address: {c.get('address1', '')} {c.get('city', '')} {c.get('state', '')} {c.get('postal_code', '')}\n"
        f"Contacts:\n" + "\n".join(contact_lines) + "\n"
        f"Notes: {c.get('public_notes', 'None')}\nPrivate Notes: {c.get('private_notes', 'None')}"
    )


@mcp.tool()
async def create_client(name: str, contact_first_name: str = "", contact_last_name: str = "",
    contact_email: str = "", contact_phone: str = "", address: str = "",
    city: str = "", state: str = "", postal_code: str = "",
    notes: str = "", private_notes: str = "") -> str:
    """Create a new client record.
    
    Args:
        name: Client/company name (e.g. family name for nanny clients)
        contact_first_name: Primary contact first name
        contact_last_name: Primary contact last name
        contact_email: Primary contact email
        contact_phone: Primary contact phone
        address: Street address
        city: City
        state: State
        postal_code: ZIP code
        notes: Public notes (visible to client)
        private_notes: Private notes (internal only)
    """
    payload = {
        "name": name,
        "contacts": [{"first_name": contact_first_name, "last_name": contact_last_name,
                      "email": contact_email, "phone": contact_phone}],
        "address1": address, "city": city, "state": state, "postal_code": postal_code,
        "country_id": "840", "public_notes": notes, "private_notes": private_notes,
    }
    result = await api_post("clients", payload)
    c = result.get("data", {})
    return f"Client created: **{c.get('name')}** (ID: {c['id']})"


@mcp.tool()
async def update_client(client_id: str, name: str = None, contact_email: str = None,
    contact_phone: str = None, address: str = None, city: str = None,
    state: str = None, notes: str = None, private_notes: str = None) -> str:
    """Update an existing client's information.
    
    Args:
        client_id: The Invoice Ninja client ID
        name: New client name (optional)
        contact_email: New email (optional)
        contact_phone: New phone (optional)
        address: New address (optional)
        city: New city (optional)
        state: New state (optional)
        notes: New public notes (optional)
        private_notes: New private notes (optional)
    """
    existing = await api_get(f"clients/{client_id}")
    client_data = existing.get("data", {})
    payload = {}
    if name: payload["name"] = name
    if address: payload["address1"] = address
    if city: payload["city"] = city
    if state: payload["state"] = state
    if notes is not None: payload["public_notes"] = notes
    if private_notes is not None: payload["private_notes"] = private_notes
    if contact_email or contact_phone:
        contacts = client_data.get("contacts", [{}])
        if contacts:
            if contact_email: contacts[0]["email"] = contact_email
            if contact_phone: contacts[0]["phone"] = contact_phone
        payload["contacts"] = contacts
    result = await api_put(f"clients/{client_id}", payload)
    c = result.get("data", {})
    return f"Client updated: **{c.get('name')}** (ID: {c['id']})"


# ============================================================
# INVOICE TOOLS
# ============================================================

@mcp.tool()
async def list_invoices(client_id: str = "", status: str = "", per_page: int = 20, page: int = 1) -> str:
    """List invoices, optionally filtered by client or status.
    
    Args:
        client_id: Filter by client ID (optional)
        status: Filter by status: draft, sent, paid, partial, overdue, cancelled (optional)
        per_page: Results per page
        page: Page number
    """
    params = {"per_page": per_page, "page": page, "include": "client"}
    if client_id: params["client_id"] = client_id
    if status:
        status_map = {"draft": "1", "sent": "2", "paid": "4", "partial": "3", "cancelled": "5", "overdue": "6"}
        params["client_status"] = status_map.get(status, status)
    result = await api_get("invoices", params)
    invoices = result.get("data", [])
    if not invoices:
        return "No invoices found."
    lines = [f"Found {len(invoices)} invoice(s):\n"]
    for inv in invoices:
        client_name = inv.get("client", {}).get("name", "Unknown")
        status_id = inv.get("status_id", "0")
        status_labels = {"1": "Draft", "2": "Sent", "3": "Partial", "4": "Paid", "5": "Cancelled", "6": "Overdue"}
        status_label = status_labels.get(str(status_id), f"Status {status_id}")
        lines.append(f"- **#{inv.get('number', 'N/A')}** — {client_name}\n  Amount: ${inv.get('amount', 0):.2f} | Balance: ${inv.get('balance', 0):.2f} | Status: {status_label} | Date: {inv.get('date', 'N/A')} | ID: {inv['id']}")
    return "\n".join(lines)


@mcp.tool()
async def create_invoice(client_id: str, items: list[dict], due_date: str = "",
    notes: str = "", send_email: bool = False) -> str:
    """Create a new invoice for a client.
    
    Args:
        client_id: The client to invoice
        items: List of line items, each with: description, quantity, unit_cost
               Example: [{"description": "Childcare - 4 hours", "quantity": 4, "unit_cost": 25.00}]
        due_date: Due date in YYYY-MM-DD format (optional)
        notes: Public notes shown on invoice (optional)
        send_email: Whether to email the invoice immediately (default False)
    """
    line_items = []
    for item in items:
        line_items.append({
            "product_key": item.get("product_key", ""),
            "notes": item.get("description", item.get("notes", "")),
            "quantity": item.get("quantity", 1),
            "cost": item.get("unit_cost", item.get("cost", 0)),
        })
    payload = {"client_id": client_id, "line_items": line_items,
               "date": datetime.now().strftime("%Y-%m-%d"), "public_notes": notes}
    if due_date: payload["due_date"] = due_date
    result = await api_post("invoices", payload)
    inv = result.get("data", {})
    if send_email and inv.get("id"):
        try:
            await api_post("invoices/bulk", {"action": "send_email", "ids": [inv["id"]]})
        except Exception as e:
            return f"Invoice created: **#{inv.get('number')}** for ${inv.get('amount', 0):.2f} (ID: {inv['id']})\n⚠️ Email send failed: {e}"
    return (f"Invoice created: **#{inv.get('number')}** for ${inv.get('amount', 0):.2f} (ID: {inv['id']})"
            + (" — Email sent!" if send_email else " — Draft (not yet sent)"))


@mcp.tool()
async def send_invoice(invoice_id: str) -> str:
    """Send an invoice via email to the client.
    
    Args:
        invoice_id: The invoice ID to send
    """
    await api_post("invoices/bulk", {"action": "send_email", "ids": [invoice_id]})
    return "Invoice sent successfully."


@mcp.tool()
async def create_recurring_invoice(client_id: str, items: list[dict],
    frequency: str = "monthly", start_date: str = "", notes: str = "") -> str:
    """Create a recurring invoice that auto-generates on a schedule.
    
    Args:
        client_id: The client to bill
        items: List of line items with description, quantity, unit_cost
        frequency: Billing frequency — weekly, biweekly, monthly, quarterly, yearly
        start_date: When to start (YYYY-MM-DD, defaults to today)
        notes: Public notes
    """
    freq_map = {"weekly": 1, "biweekly": 2, "monthly": 4, "quarterly": 8, "yearly": 32}
    line_items = []
    for item in items:
        line_items.append({
            "product_key": item.get("product_key", ""),
            "notes": item.get("description", item.get("notes", "")),
            "quantity": item.get("quantity", 1),
            "cost": item.get("unit_cost", item.get("cost", 0)),
        })
    payload = {"client_id": client_id, "line_items": line_items,
               "frequency_id": freq_map.get(frequency, 4),
               "next_send_date": start_date or datetime.now().strftime("%Y-%m-%d"),
               "auto_bill": "always", "public_notes": notes}
    result = await api_post("recurring_invoices", payload)
    ri = result.get("data", {})
    return f"Recurring invoice created (ID: {ri['id']})\nFrequency: {frequency} | Next send: {ri.get('next_send_date', 'N/A')} | Amount: ${ri.get('amount', 0):.2f}"


# ============================================================
# PAYMENT TOOLS
# ============================================================

@mcp.tool()
async def record_payment(invoice_id: str, amount: float = 0,
    payment_type: str = "cash", notes: str = "") -> str:
    """Record a payment against an invoice.
    
    Args:
        invoice_id: The invoice being paid
        amount: Payment amount (0 = full invoice amount)
        payment_type: Payment method — cash, check, credit_card, bank_transfer, venmo, zelle
        notes: Payment notes
    """
    if amount == 0:
        inv = await api_get(f"invoices/{invoice_id}")
        amount = inv.get("data", {}).get("balance", 0)
    type_map = {"cash": "32", "check": "16", "credit_card": "1",
                "bank_transfer": "2", "venmo": "46", "zelle": "47"}
    payload = {"amount": amount, "invoices": [{"invoice_id": invoice_id, "amount": amount}],
               "type_id": type_map.get(payment_type, "32"),
               "date": datetime.now().strftime("%Y-%m-%d"), "private_notes": notes}
    result = await api_post("payments", payload)
    p = result.get("data", {})
    return f"Payment recorded: ${amount:.2f} via {payment_type} (Payment ID: {p['id']})"


@mcp.tool()
async def list_payments(client_id: str = "", per_page: int = 20) -> str:
    """List recent payments, optionally filtered by client.
    
    Args:
        client_id: Filter by client ID (optional)
        per_page: Results per page
    """
    params = {"per_page": per_page, "include": "client,invoices"}
    if client_id: params["client_id"] = client_id
    result = await api_get("payments", params)
    payments = result.get("data", [])
    if not payments:
        return "No payments found."
    lines = [f"Found {len(payments)} payment(s):\n"]
    for p in payments:
        client_name = p.get("client", {}).get("name", "Unknown")
        lines.append(f"- ${p.get('amount', 0):.2f} from {client_name} on {p.get('date', 'N/A')} (ID: {p['id']})")
    return "\n".join(lines)


# ============================================================
# QUOTE / PROPOSAL TOOLS
# ============================================================

@mcp.tool()
async def create_quote(client_id: str, items: list[dict], valid_until: str = "", notes: str = "") -> str:
    """Create a quote/proposal for a client.
    
    Args:
        client_id: The client to quote
        items: List of line items with description, quantity, unit_cost
        valid_until: Quote expiry date (YYYY-MM-DD, optional)
        notes: Public notes on the quote
    """
    line_items = []
    for item in items:
        line_items.append({
            "product_key": item.get("product_key", ""),
            "notes": item.get("description", item.get("notes", "")),
            "quantity": item.get("quantity", 1),
            "cost": item.get("unit_cost", item.get("cost", 0)),
        })
    payload = {"client_id": client_id, "line_items": line_items,
               "date": datetime.now().strftime("%Y-%m-%d"), "public_notes": notes}
    if valid_until: payload["valid_until"] = valid_until
    result = await api_post("quotes", payload)
    q = result.get("data", {})
    return f"Quote created: **#{q.get('number')}** for ${q.get('amount', 0):.2f} (ID: {q['id']})"


@mcp.tool()
async def convert_quote_to_invoice(quote_id: str) -> str:
    """Convert an approved quote into an invoice.
    
    Args:
        quote_id: The quote ID to convert
    """
    await api_post("quotes/bulk", {"action": "convert_to_invoice", "ids": [quote_id]})
    return "Quote converted to invoice successfully."


# ============================================================
# DASHBOARD / REPORTING TOOLS
# ============================================================

@mcp.tool()
async def get_dashboard() -> str:
    """Get a business dashboard summary — revenue, outstanding balances, recent activity."""
    invoices = await api_get("invoices", {"per_page": 100, "include": "client"})
    inv_data = invoices.get("data", [])
    payments = await api_get("payments", {"per_page": 100})
    pay_data = payments.get("data", [])
    clients = await api_get("clients", {"per_page": 100})
    cli_data = clients.get("data", [])
    total_invoiced = sum(i.get("amount", 0) for i in inv_data)
    total_outstanding = sum(i.get("balance", 0) for i in inv_data if i.get("balance", 0) > 0)
    total_paid = sum(p.get("amount", 0) for p in pay_data)
    active_clients = len(cli_data)
    today = datetime.now().strftime("%Y-%m-%d")
    overdue = [i for i in inv_data if i.get("due_date", "9999") < today and i.get("balance", 0) > 0]
    lines = ["📊 **Business Dashboard**\n", f"**Clients:** {active_clients} active",
             f"**Total Invoiced:** ${total_invoiced:.2f}", f"**Total Paid:** ${total_paid:.2f}",
             f"**Outstanding:** ${total_outstanding:.2f}", f"**Overdue Invoices:** {len(overdue)}"]
    if overdue:
        lines.append("\n**⚠️ Overdue:**")
        for inv in overdue[:5]:
            client_name = inv.get("client", {}).get("name", "Unknown")
            lines.append(f"  - #{inv.get('number')} — {client_name}: ${inv.get('balance', 0):.2f} (due {inv.get('due_date')})")
    return "\n".join(lines)


@mcp.tool()
async def get_client_statement(client_id: str) -> str:
    """Get a complete statement for a client — all invoices and payments.
    
    Args:
        client_id: The client ID
    """
    client = await api_get(f"clients/{client_id}")
    c = client.get("data", {})
    invoices = await api_get("invoices", {"client_id": client_id, "per_page": 50})
    inv_data = invoices.get("data", [])
    payments = await api_get("payments", {"client_id": client_id, "per_page": 50})
    pay_data = payments.get("data", [])
    lines = [f"📄 **Statement for {c.get('name', 'Unknown')}**\n",
             f"Total Paid: ${c.get('paid_to_date', 0):.2f}",
             f"Current Balance: ${c.get('balance', 0):.2f}\n", "**Invoices:**"]
    for inv in inv_data:
        status_labels = {"1": "Draft", "2": "Sent", "3": "Partial", "4": "Paid", "5": "Cancelled"}
        status = status_labels.get(str(inv.get("status_id", 0)), "Unknown")
        lines.append(f"  - #{inv.get('number')} | {inv.get('date')} | ${inv.get('amount', 0):.2f} | {status}")
    if pay_data:
        lines.append("\n**Payments:**")
        for p in pay_data:
            lines.append(f"  - ${p.get('amount', 0):.2f} on {p.get('date', 'N/A')}")
    return "\n".join(lines)


# ============================================================
# EXPENSE TOOLS
# ============================================================

@mcp.tool()
async def create_expense(amount: float, category: str = "", vendor: str = "",
    notes: str = "", date: str = "") -> str:
    """Record a business expense.
    
    Args:
        amount: Expense amount
        category: Expense category (e.g. "supplies", "mileage", "food")
        vendor: Vendor/payee name
        notes: Description of expense
        date: Date of expense (YYYY-MM-DD, defaults to today)
    """
    payload = {"amount": amount, "public_notes": notes,
               "private_notes": f"Category: {category}" if category else "",
               "vendor_id": "", "date": date or datetime.now().strftime("%Y-%m-%d")}
    result = await api_post("expenses", payload)
    e = result.get("data", {})
    return f"Expense recorded: ${amount:.2f} — {notes or category} (ID: {e['id']})"


@mcp.tool()
async def list_expenses(per_page: int = 20) -> str:
    """List recent expenses.
    
    Args:
        per_page: Results per page
    """
    result = await api_get("expenses", {"per_page": per_page})
    expenses = result.get("data", [])
    if not expenses:
        return "No expenses found."
    total = sum(e.get("amount", 0) for e in expenses)
    lines = [f"Found {len(expenses)} expense(s) (total: ${total:.2f}):\n"]
    for e in expenses:
        lines.append(f"- ${e.get('amount', 0):.2f} on {e.get('date', 'N/A')} — {e.get('public_notes', 'No description')} (ID: {e['id']})")
    return "\n".join(lines)


# ============================================================
# PRODUCT / SERVICE TOOLS
# ============================================================

@mcp.tool()
async def create_product(product_key: str, description: str, price: float) -> str:
    """Create a reusable product/service for quick invoicing.
    
    Args:
        product_key: Short name/code (e.g. "childcare-hourly", "date-night")
        description: Full description shown on invoices
        price: Default unit price
    """
    payload = {"product_key": product_key, "notes": description, "price": price}
    result = await api_post("products", payload)
    p = result.get("data", {})
    return f"Product created: **{product_key}** at ${price:.2f} (ID: {p['id']})"


@mcp.tool()
async def list_products() -> str:
    """List all products/services available for invoicing."""
    result = await api_get("products", {"per_page": 50})
    products = result.get("data", [])
    if not products:
        return "No products/services defined yet."
    lines = ["**Products/Services:**\n"]
    for p in products:
        lines.append(f"- **{p.get('product_key', 'N/A')}** — {p.get('notes', 'No description')} (${p.get('price', 0):.2f}) ID: {p['id']}")
    return "\n".join(lines)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    mcp.run(transport=transport)
