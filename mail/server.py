"""mail MCP Server — JMAP/SMTP for Stalwart Mail Server.
Accounts: jerry, notifications, postmaster @millyweb.com
Tools: mail_send, mail_read, mail_get, mail_search, mail_list_mailboxes
"""
import json, base64, smtplib, os, requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

STALWART_HOST = "stalwart-mail"
STALWART_JMAP = f"http://{STALWART_HOST}:8080/jmap"
STALWART_SMTP_HOST = STALWART_HOST
STALWART_SMTP_PORT = 587

ACCOUNTS = {
    "jerry":         {"email": "jerry@millyweb.com",         "password": os.environ.get("JERRY_PASSWORD", "")},
    "notifications": {"email": "notifications@millyweb.com", "password": os.environ.get("NOTIFICATIONS_PASSWORD", "")},
    "postmaster":    {"email": "postmaster@millyweb.com",    "password": os.environ.get("POSTMASTER_PASSWORD", "")},
}

mcp = FastMCP("mcp-mail", instructions="Email tools for sending and reading mail via Stalwart Mail Server",
              transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False))

def _jmap_call(account: str, method_calls: list) -> dict:
    acct = ACCOUNTS.get(account)
    if not acct: raise ValueError(f"Unknown account: {account}")
    auth = base64.b64encode(f"{account}:{acct['password']}".encode()).decode()
    resp = requests.post(STALWART_JMAP, json={"using": ["urn:ietf:params:jmap:core", "urn:ietf:params:jmap:mail"], "methodCalls": method_calls},
                         headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json"}, timeout=30)
    resp.raise_for_status()
    return resp.json()

@mcp.tool()
def mail_send(to: str, subject: str, body: str, from_account: str = "jerry", html: bool = False, cc: str = "", reply_to: str = "") -> str:
    """Send email from a Millyweb account. from_account: jerry, notifications, postmaster."""
    acct = ACCOUNTS.get(from_account)
    if not acct: return f"Error: Unknown account '{from_account}'"
    try:
        msg = MIMEMultipart("alternative") if html else MIMEText(body)
        if html: msg.attach(MIMEText(body, "html"))
        msg["Subject"] = subject; msg["From"] = acct["email"]; msg["To"] = to
        if cc: msg["Cc"] = cc
        if reply_to: msg["Reply-To"] = reply_to
        recipients = [a.strip() for a in to.split(",")]
        if cc: recipients += [a.strip() for a in cc.split(",")]
        with smtplib.SMTP(STALWART_SMTP_HOST, STALWART_SMTP_PORT, timeout=30) as s:
            s.ehlo("mail.millyweb.com"); s.starttls(); s.login(from_account, acct["password"])
            s.sendmail(acct["email"], recipients, msg.as_string())
        return f"\u2713 Sent from {acct['email']} to {to}" + (f" (cc: {cc})" if cc else "")
    except Exception as e: return f"\u2717 Send failed: {e}"

@mcp.tool()
def mail_read(account: str = "jerry", limit: int = 10, mailbox: str = "Inbox", unread_only: bool = False) -> str:
    """Read emails. account: jerry, notifications, postmaster. mailbox: Inbox, Sent, Junk Mail, Drafts, Trash."""
    try:
        result = _jmap_call(account, [["Mailbox/get", {"properties": ["name", "id", "totalEmails", "unreadEmails"]}, "mb"]])
        mailboxes = result["methodResponses"][0][1].get("list", [])
        target_mb = next((mb for mb in mailboxes if mb["name"].lower() == mailbox.lower()), None)
        if not target_mb: return f"Mailbox '{mailbox}' not found. Available: {[mb['name'] for mb in mailboxes]}"
        filter_obj = {"inMailbox": target_mb["id"]}
        if unread_only: filter_obj["notKeyword"] = "$seen"
        result = _jmap_call(account, [
            ["Email/query", {"filter": filter_obj, "sort": [{"property": "receivedAt", "isAscending": False}], "limit": min(max(limit, 1), 50)}, "eq"],
            ["Email/get", {"#ids": {"resultOf": "eq", "name": "Email/query", "path": "/ids"}, "properties": ["id", "from", "to", "subject", "receivedAt", "preview", "keywords", "size"]}, "eg"]
        ])
        emails = result["methodResponses"][1][1].get("list", [])
        if not emails: return f"No {'unread ' if unread_only else ''}emails in {mailbox}"
        output = [f"\U0001f4ec {account}@millyweb.com \u2014 {mailbox} ({target_mb.get('totalEmails',0)} total, {target_mb.get('unreadEmails',0)} unread)\n"]
        for i, email in enumerate(emails, 1):
            fr = email.get("from", [{}])[0]; is_read = "$seen" in email.get("keywords", {})
            output.append(f"{'\U0001f4d6' if is_read else '\U0001f4e9'} {i}. {email.get('subject','(no subject)')}\n   From: {fr.get('name') or fr.get('email','?')} | {email.get('receivedAt','')[:16]}\n   {email.get('preview','')[:200]}\n   ID: {email['id']}")
        return "\n".join(output)
    except Exception as e: return f"\u2717 Read failed: {e}"

@mcp.tool()
def mail_get(email_id: str, account: str = "jerry") -> str:
    """Get full content of a specific email by ID."""
    try:
        result = _jmap_call(account, [["Email/get", {"ids": [email_id], "properties": ["id", "from", "to", "cc", "subject", "receivedAt", "textBody", "htmlBody", "bodyValues", "attachments"], "fetchAllBodyValues": True}, "eg"]])
        emails = result["methodResponses"][0][1].get("list", [])
        if not emails: return f"Email {email_id} not found"
        email = emails[0]; fr = email.get("from", [{}])[0]
        to_addrs = ", ".join(a.get("email", "") for a in email.get("to", []))
        body_values = email.get("bodyValues", {}); body_text = ""
        for part in email.get("textBody", []):
            pid = part.get("partId")
            if pid and pid in body_values: body_text += body_values[pid].get("value", "")
        atts = email.get("attachments", [])
        att_str = "".join(f"\n   - {a.get('name','unnamed')} ({a.get('type','?')}, {a.get('size',0)} bytes)" for a in atts)
        return f"\U0001f4e7 {email.get('subject','(no subject)')}\nFrom: {fr.get('name','')} <{fr.get('email','')}>\nTo: {to_addrs}\nDate: {email.get('receivedAt','')}\n{'\U0001f4ce Attachments:' + att_str if atts else ''}\n\n---\n{body_text}"
    except Exception as e: return f"\u2717 Get failed: {e}"

@mcp.tool()
def mail_search(query: str, account: str = "jerry", limit: int = 10) -> str:
    """Search emails by text content, subject, or sender."""
    try:
        result = _jmap_call(account, [
            ["Email/query", {"filter": {"text": query}, "sort": [{"property": "receivedAt", "isAscending": False}], "limit": min(limit, 50)}, "eq"],
            ["Email/get", {"#ids": {"resultOf": "eq", "name": "Email/query", "path": "/ids"}, "properties": ["id", "from", "to", "subject", "receivedAt", "preview"]}, "eg"]
        ])
        emails = result["methodResponses"][1][1].get("list", [])
        if not emails: return f"No results for '{query}'"
        lines = [f"\U0001f50d '{query}' in {account}@millyweb.com:\n"]
        for i, email in enumerate(emails, 1):
            fr = email.get("from", [{}])[0]
            lines.append(f"{i}. {email.get('subject','(no subject)')}\n   From: {fr.get('name') or fr.get('email','?')} | {email.get('receivedAt','')[:16]}\n   {email.get('preview','')[:150]}\n   ID: {email['id']}")
        return "\n".join(lines)
    except Exception as e: return f"\u2717 Search failed: {e}"

@mcp.tool()
def mail_list_mailboxes(account: str = "jerry") -> str:
    """List all mailboxes/folders for an account."""
    try:
        result = _jmap_call(account, [["Mailbox/get", {"properties": ["name", "id", "totalEmails", "unreadEmails", "role"]}, "mb"]])
        mailboxes = result["methodResponses"][0][1].get("list", [])
        lines = [f"\U0001f4c1 Mailboxes for {account}@millyweb.com:\n"]
        for mb in sorted(mailboxes, key=lambda x: x.get("name", "")):
            unread = mb.get("unreadEmails", 0)
            lines.append(f"  {mb['name']}{' (' + mb['role'] + ')' if mb.get('role') else ''}: {mb.get('totalEmails',0)} emails{' \U0001f4e9' + str(unread) if unread else ''} [id: {mb['id']}]")
        return "\n".join(lines)
    except Exception as e: return f"\u2717 List failed: {e}"

if __name__ == "__main__":
    import uvicorn
    from starlette.middleware.trustedhost import TrustedHostMiddleware
    app = mcp.sse_app()
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])
    uvicorn.run(app, host="0.0.0.0", port=8000)
