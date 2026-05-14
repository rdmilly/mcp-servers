# mcp-servers

All custom MW MCP integration servers. One folder per server.
Registered and managed by the MCP Provisioner at mcp.millyweb.com.

| Server | Tools | Description |
|--------|-------|-------------|
| `mcp-workdocs` | workdocs_read, workdocs_write, workdocs_search | Working KB docs, journals, specs |
| `mcp-cloudflare-dns` | dns_list, dns_create, dns_update, dns_delete | DNS management |
| `mcp-telegram` | send_message, send_alert | Telegram notifications |
| `mcp-github-projects` | create_issue, list_issues, update_issue | GitHub project management |
| `mcp-infisical` | get_secret, set_secret, list_secrets | Secrets management |
| `mcp-kb-gateway` | kb_search, kb_read | Infra knowledge base |
| `mcp-mail` | send_email, list_inbox | Mail operations |
| `mcp-invoice-ninja` | create_invoice, list_clients | Invoicing |
| `mcp-provision-filter` | filter_tools | MCP tool filtering layer |
| `mcp-transfer` | transfer_upload, transfer_download | File transfer |

## Add a server

```bash
mkdir new-server && cd new-server
# Write server.py, Dockerfile, requirements.txt
# Register with Provisioner
```
