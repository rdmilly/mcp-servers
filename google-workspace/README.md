# google-workspace MCP server

Full Google Workspace MCP server — Gmail, Drive, Calendar, Docs, Sheets, Slides, Forms, Tasks, Chat, and Search via a single FastMCP streamable-HTTP server.

**Source:** Fork of [`taylorwilsdon/google_workspace_mcp`](https://github.com/taylorwilsdon/google_workspace_mcp) (MIT license, v1.6.2)
**85 tools** across 10 Google services.

## Services

| Service | Module | Key tools |
|---|---|---|
| Gmail | `gmail/` | send, read, search, labels, drafts, attachments |
| Drive | `gdrive/` | list, search, read, upload, share, move |
| Calendar | `gcalendar/` | list events, create, update, delete, attendees |
| Docs | `gdocs/` | read, create, insert, tables, comments |
| Sheets | `gsheets/` | read/write cells, create, format, formulas |
| Slides | `gslides/` | create, add slides, shapes, text, images |
| Forms | `gforms/` | create forms, add questions, get responses |
| Tasks | `gtasks/` | list, create, complete, delete tasks |
| Chat | `gchat/` | send messages, list spaces |
| Search | `gsearch/` | Google Custom Search |

## Config

| Env var | Description |
|---|---|
| `GOOGLE_OAUTH_CLIENT_ID` | OAuth client ID |
| `GOOGLE_OAUTH_CLIENT_SECRET` | OAuth client secret |
| `USER_GOOGLE_EMAIL` | Default user email (single-user mode) |
| `MCP_ENABLE_OAUTH21` | Enable multi-user OAuth 2.1 mode |
| `TOOL_TIER` | `core` / `extended` / `complete` |
| `TOOLS` | Space-separated list of services to load |
| `OAUTHLIB_INSECURE_TRANSPORT` | `1` for HTTP dev (disable in prod) |

Credentials persist across restarts via the `mcp-google-workspace-creds` named Docker volume at `/app/store_creds`.

## Deploy

```bash
docker run -d \
  -p 8092:8000 \
  -e GOOGLE_OAUTH_CLIENT_ID=... \
  -e GOOGLE_OAUTH_CLIENT_SECRET=... \
  -e OAUTHLIB_INSECURE_TRANSPORT=1 \
  -v mcp-google-workspace-creds:/app/store_creds \
  --network mcp-network \
  mcp-google-workspace_mcp-google-workspace \
  uv run main.py --transport streamable-http
```

Registered in mcp-provisioner at port 8092, WARM pool, 15-min idle timeout.
