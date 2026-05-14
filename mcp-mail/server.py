"""
MCP Mail Server - JMAP/SMTP email tools for Jerry
Connects to Stalwart Mail Server via JMAP API and SMTP
"""
import json
import base64
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from mcp.server.fastmcp import FastMCP

# Stalwart connection (resolved via Docker network)
STALWART_HOST = "stalwart-mail"
STALWART_JMAP = f"http://{STALWART_HOST}:8080/jmap"
STALWART_SMTP_HOST = STALWART_HOST
STALWART_SMTP_PORT = 587

# Default accounts - credentials injected via env
import os
ACCOUNTS = {
    "jerry": {
        "email": "jerry@millyweb.com",
        "password": os.environ.get("JERRY_PASSWORD", ""),
    },
    "notifications": {
        "email": "notifications@millyweb.com", 
        "password": os.environ.get("NOTIFICATIONS_PASSWORD", ""),
    },
    "postmaster": {
        "email": "postmaster@millyweb.com",
        "password": os.environ.get("POSTMASTER_PASSWORD", ""),
    },
}

from mcp.server.transport_security import TransportSecuritySettings
mcp = FastMCP("mcp-mail", instructions="Email tools for sending and reading mail via Stalwart Mail Server", transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False))


def _jmap_call(account: str, method_calls: list) -> dict:
    """Make a JMAP API call with Basic auth."""
    acct = ACCOUNTS.get(account)
    if not acct:
        raise ValueError(f"Unknown account: {account}. Available: {list(ACCOUNTS.keys())}")
    
    auth = base64.b64encode(f"{account}:{acct['password']}".encode()).decode()
    
    payload = {
        "using": [
            "urn:ietf:params:jmap:core",
            "urn:ietf:params:jmap:mail",
            "urn:ietf:params:jmap:submission"
        ],
        "methodCalls": method_calls
    }
    
    resp = requests.post(
        STALWART_JMAP,
        json=payload,
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/json"
        },
        timeout=30
    )
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def mail_send(
    to: str,
    subject: str,
    body: str,
    from_account: str = "jerry",
    html: bool = False,
    cc: str = "",
    reply_to: str = ""
) -> str:
    """Send an email from a Millyweb account.
    
    Args:
        to: Recipient email address (comma-separated for multiple)
        subject: Email subject line
        body: Email body (plain text or HTML)
        from_account: Account to send from: jerry, notifications, postmaster
        html: If True, body is treated as HTML
        cc: CC recipients (comma-separated)
        reply_to: Reply-To address
    """
    acct = ACCOUNTS.get(from_account)
    if not acct:
        return f"Error: Unknown account '{from_account}'. Available: {list(ACCOUNTS.keys())}"
    
    try:
        if html:
            msg = MIMEMultipart("alternative")
            msg.attach(MIMEText(body, "html"))
        else:
            msg = MIMEText(body)
        
        msg["Subject"] = subject
        msg["From"] = acct["email"]
        msg["To"] = to
        if cc:
            msg["Cc"] = cc
        if reply_to:
            msg["Reply-To"] = reply_to
        
        recipients = [addr.strip() for addr in to.split(",")]
        if cc:
            recipients.extend([addr.strip() for addr in cc.split(",")])
        
        with smtplib.SMTP(STALWART_SMTP_HOST, STALWART_SMTP_PORT, timeout=30) as server:
            server.ehlo("mail.millyweb.com")
            server.starttls()
            server.login(from_account, acct["password"])
            server.sendmail(acct["email"], recipients, msg.as_string())
        
        return f"✓ Sent from {acct['email']} to {to}" + (f" (cc: {cc})" if cc else "")
    
    except Exception as e:
        return f"✗ Send failed: {str(e)}"


@mcp.tool()
def mail_read(
    account: str = "jerry",
    limit: int = 10,
    mailbox: str = "Inbox",
    unread_only: bool = False
) -> str:
    """Read emails from a Millyweb mailbox.
    
    Args:
        account: Account to read from: jerry, notifications, postmaster
        limit: Max number of emails to return (1-50)
        mailbox: Mailbox name (Inbox, Sent, Junk Mail, Drafts, Trash)
        unread_only: Only return unread messages
    """
    try:
        # First get mailbox IDs
        result = _jmap_call(account, [
            ["Mailbox/get", {"properties": ["name", "id", "totalEmails", "unreadEmails"]}, "mb"]
        ])
        
        mailboxes = result["methodResponses"][0][1].get("list", [])
        target_mb = None
        for mb in mailboxes:
            if mb["name"].lower() == mailbox.lower():
                target_mb = mb
                break
        
        if not target_mb:
            mb_names = [mb["name"] for mb in mailboxes]
            return f"Mailbox '{mailbox}' not found. Available: {mb_names}"
        
        # Build filter
        filter_obj = {"inMailbox": target_mb["id"]}
        if unread_only:
            filter_obj["notKeyword"] = "$seen"
        
        # Query emails
        limit = min(max(limit, 1), 50)
        result = _jmap_call(account, [
            ["Email/query", {
                "filter": filter_obj,
                "sort": [{"property": "receivedAt", "isAscending": False}],
                "limit": limit
            }, "eq"],
            ["Email/get", {
                "#ids": {"resultOf": "eq", "name": "Email/query", "path": "/ids"},
                "properties": ["id", "from", "to", "subject", "receivedAt", "preview", "keywords", "size"]
            }, "eg"]
        ])
        
        emails = result["methodResponses"][1][1].get("list", [])
        
        if not emails:
            return f"No {'unread ' if unread_only else ''}emails in {mailbox} for {account}@millyweb.com"
        
        output = [f"📬 {account}@millyweb.com — {mailbox} ({target_mb.get('totalEmails', 0)} total, {target_mb.get('unreadEmails', 0)} unread)\n"]
        
        for i, email in enumerate(emails, 1):
            from_addr = email.get("from", [{}])[0]
            from_str = from_addr.get("name") or from_addr.get("email", "unknown")
            is_read = "$seen" in email.get("keywords", {})
            read_icon = "📖" if is_read else "📩"
            
            output.append(
                f"{read_icon} {i}. **{email.get('subject', '(no subject)')}**\n"
                f"   From: {from_str} | {email.get('receivedAt', '')[:16]}\n"
                f"   {email.get('preview', '')[:200]}\n"
                f"   ID: {email['id']}"
            )
        
        return "\n".join(output)
    
    except Exception as e:
        return f"✗ Read failed: {str(e)}"


@mcp.tool()
def mail_get(email_id: str, account: str = "jerry") -> str:
    """Get full content of a specific email by ID.
    
    Args:
        email_id: The email ID (from mail_read results)
        account: Account the email belongs to
    """
    try:
        result = _jmap_call(account, [
            ["Email/get", {
                "ids": [email_id],
                "properties": ["id", "from", "to", "cc", "subject", "receivedAt", "textBody", "htmlBody", "bodyValues", "attachments", "headers"],
                "fetchAllBodyValues": True
            }, "eg"]
        ])
        
        emails = result["methodResponses"][0][1].get("list", [])
        if not emails:
            return f"Email {email_id} not found"
        
        email = emails[0]
        from_addr = email.get("from", [{}])[0]
        to_addrs = ", ".join([a.get("email", "") for a in email.get("to", [])])
        cc_addrs = ", ".join([a.get("email", "") for a in email.get("cc", [])])
        
        # Get body text
        body_values = email.get("bodyValues", {})
        body_text = ""
        for part in email.get("textBody", []):
            part_id = part.get("partId")
            if part_id and part_id in body_values:
                body_text += body_values[part_id].get("value", "")
        
        if not body_text:
            for part in email.get("htmlBody", []):
                part_id = part.get("partId")
                if part_id and part_id in body_values:
                    body_text += body_values[part_id].get("value", "")
        
        attachments = email.get("attachments", [])
        att_str = f"\n📎 Attachments: {len(attachments)}" if attachments else ""
        for att in attachments:
            att_str += f"\n   - {att.get('name', 'unnamed')} ({att.get('type', 'unknown')}, {att.get('size', 0)} bytes)"
        
        output = (
            f"📧 **{email.get('subject', '(no subject)')}**\n"
            f"From: {from_addr.get('name', '')} <{from_addr.get('email', '')}>\n"
            f"To: {to_addrs}\n"
            f"{'Cc: ' + cc_addrs if cc_addrs else ''}"
            f"Date: {email.get('receivedAt', '')}\n"
            f"{att_str}\n"
            f"\n---\n{body_text}"
        )
        
        return output
    
    except Exception as e:
        return f"✗ Get failed: {str(e)}"


@mcp.tool()
def mail_search(
    query: str,
    account: str = "jerry",
    limit: int = 10
) -> str:
    """Search emails by text content, subject, or sender.
    
    Args:
        query: Search text (searches subject, body, from, to)
        account: Account to search in
        limit: Max results
    """
    try:
        result = _jmap_call(account, [
            ["Email/query", {
                "filter": {"text": query},
                "sort": [{"property": "receivedAt", "isAscending": False}],
                "limit": min(limit, 50)
            }, "eq"],
            ["Email/get", {
                "#ids": {"resultOf": "eq", "name": "Email/query", "path": "/ids"},
                "properties": ["id", "from", "to", "subject", "receivedAt", "preview"]
            }, "eg"]
        ])
        
        emails = result["methodResponses"][1][1].get("list", [])
        
        if not emails:
            return f"No results for '{query}' in {account}@millyweb.com"
        
        output = [f"🔍 Search results for '{query}' in {account}@millyweb.com:\n"]
        for i, email in enumerate(emails, 1):
            from_addr = email.get("from", [{}])[0]
            from_str = from_addr.get("name") or from_addr.get("email", "unknown")
            output.append(
                f"{i}. **{email.get('subject', '(no subject)')}**\n"
                f"   From: {from_str} | {email.get('receivedAt', '')[:16]}\n"
                f"   {email.get('preview', '')[:150]}\n"
                f"   ID: {email['id']}"
            )
        
        return "\n".join(output)
    
    except Exception as e:
        return f"✗ Search failed: {str(e)}"


@mcp.tool()
def mail_list_mailboxes(account: str = "jerry") -> str:
    """List all mailboxes/folders for an account.
    
    Args:
        account: Account to list mailboxes for
    """
    try:
        result = _jmap_call(account, [
            ["Mailbox/get", {"properties": ["name", "id", "totalEmails", "unreadEmails", "role"]}, "mb"]
        ])
        
        mailboxes = result["methodResponses"][0][1].get("list", [])
        
        output = [f"📁 Mailboxes for {account}@millyweb.com:\n"]
        for mb in sorted(mailboxes, key=lambda x: x.get("name", "")):
            role = f" ({mb['role']})" if mb.get("role") else ""
            unread = mb.get("unreadEmails", 0)
            unread_str = f" 📩{unread}" if unread > 0 else ""
            output.append(f"  {mb['name']}{role}: {mb.get('totalEmails', 0)} emails{unread_str} [id: {mb['id']}]")
        
        return "\n".join(output)
    
    except Exception as e:
        return f"✗ List failed: {str(e)}"




if __name__ == "__main__":
    import uvicorn
    from starlette.middleware.trustedhost import TrustedHostMiddleware
    app = mcp.sse_app()
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])
    uvicorn.run(app, host="0.0.0.0", port=8000)
