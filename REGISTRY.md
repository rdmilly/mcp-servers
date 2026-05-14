# Server Registry

All 48 servers managed by [mcp-provisioner](https://github.com/rdmilly/mcp-provisioner). Source in this repo = custom-built code. Third-party servers run standard packages via provisioner manifest.

**Total: 48 servers, ~740 tools**

Authoritative manifest: `/opt/projects/mcp-provisioner/config/manifest.json` on VPS2.

## HOT (always running) — 17 servers

| Server | Tools | Source |
|---|---|---|
| `helix` | 33 | [rdmilly/helix](https://github.com/rdmilly/helix) |
| `docker` | 18 | third-party `mcp-server-docker` |
| `filesystem` | 14 | third-party `server-filesystem` |
| `github` | 26 | third-party `mcp-server-github` |
| `slack` | 8 | third-party `server-slack` |
| `gateway` | 9 | ✅ [gateway/](gateway/) — archived (replaced by Lifeline) |
| `knowledgebase` | 4 | ✅ [knowledgebase/](knowledgebase/) |
| `workingdocs` | 5 | ✅ [workingdocs/](workingdocs/) |
| `minio` | 26 | third-party MinIO AIStor MCP |
| `infisical` | 7 | third-party Infisical MCP |
| `invoiceninja` | 18 | ✅ [invoice-ninja/](invoice-ninja/) |
| `cloudflare-dns` | 29 | ✅ [cloudflare-dns/](cloudflare-dns/) |
| `transfer` | 5 | ✅ [transfer/](transfer/) |
| `staging` | 4 | ✅ [staging/](staging/) |
| `printblocks` | 19 | ✅ [printblocks/](printblocks/) |
| `board` | 9 | ✅ [board/](board/) |
| `miro` | 12 | ✅ [miro/](miro/) |

## WARM (on-demand) — 31 servers

| Server | Tools | Source |
|---|---|---|
| `bravesearch` | 2 | third-party `server-brave-search` |
| `browserless` | 5 | ✅ [browserless/](browserless/) |
| `cloudflare` | 89 | third-party `@cloudflare/mcp-server-cloudflare` |
| `context7` | 2 | third-party `@upstash/context7-mcp` |
| `docker-readonly` | 19 | third-party `mcp-server-docker` (read-only) |
| `everything` | 13 | third-party `server-everything` |
| `facebook` | 11 | ✅ [facebook/](facebook/) |
| `fetch` | 1 | third-party `mcp-server-fetch` |
| `filetransfer` | 6 | ✅ [filetransfer/](filetransfer/) |
| `git` | 12 | third-party `mcp-server-git` |
| `githubprojects` | 29 | ✅ [github-projects/](github-projects/) (TypeScript — full source at `/opt/projects/mw-mcp-servers/mcp-github-projects/` on VPS2) |
| `googleworkspace` | 85 | ⚠️ full source at `/opt/repos/mcp-google-workspace/` on VPS2 — large multi-file repo, needs separate push |
| `grafana` | 44 | third-party `grafana/mcp-grafana` |
| `instantly` | 38 | third-party `instantly-mcp` |
| `linkedin` | 16 | ✅ [linkedin/](linkedin/) |
| `loki` | 6 | ✅ [loki/](loki/) (reconstructed from manifest — image not cached locally) |
| `mail` | 5 | ✅ [mail/](mail/) |
| `n8n` | 29 | ✅ [n8n/](n8n/) |
| `notion` | 22 | third-party + ✅ [notion-proxy/](notion-proxy/) (description sanitizer) |
| `postgresql` | 1 | third-party `server-postgres` |
| `prometheus` | 6 | third-party `prometheus-mcp-server` |
| `puppeteer` | 7 | third-party `mcp-server-puppeteer` |
| `qdrant` | 2 | ✅ [qdrant/](qdrant/) (reconstructed from manifest) |
| `recraft` | 9 | third-party `@recraft-ai/mcp-recraft-server` |
| `sequentialthinking` | 1 | third-party `server-sequential-thinking` |
| `sqlite` | 6 | third-party `mcp-server-sqlite` |
| `telegram` | 7 | ✅ [telegram/](telegram/) |
| `telegram-bot` | 6 | ✅ [telegram-bot/](telegram-bot/) |
| `time` | 2 | third-party `mcp-server-time` |
| `uptime-kuma` | 7 | third-party `mcp-uptime-kuma` |
| `youtube` | 6 | third-party `mcp-youtube` |

## One remaining

`googleworkspace` (85 tools) — full multi-file Python repo at `/opt/repos/mcp-google-workspace/` on VPS2. Has `main.py`, `auth/`, `core/`, `gdrive/`, `gmail/`, `gcalendar/`, `gsheets/`, `gdocs/`, `gslides/`, `gtasks/`, `gchat/`, `gforms/`, `gsearch/`. Push separately via git in a VPS2 session.
