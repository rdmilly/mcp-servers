# Server Registry

All 48 servers managed by [mcp-provisioner](https://github.com/rdmilly/mcp-provisioner). Source in this repo = custom-built code. Everything else runs a third-party package via provisioner manifest.

**Total: 48 servers, ~740 tools**

Authoritative manifest: `/opt/projects/mcp-provisioner/config/manifest.json` on VPS2.

## HOT (always running) — 17 servers

| Server | Tools | Source in this repo |
|---|---|---|
| `helix` | 33 | [rdmilly/helix](https://github.com/rdmilly/helix) |
| `docker` | 18 | third-party `mcp-server-docker` |
| `filesystem` | 14 | third-party `server-filesystem` |
| `github` | 26 | third-party `mcp-server-github` |
| `slack` | 8 | third-party `server-slack` |
| `gateway` | 9 | [gateway/](gateway/) — archived (replaced by Lifeline) |
| `knowledgebase` | 4 | ✅ [knowledgebase/](knowledgebase/) |
| `workingdocs` | 5 | ✅ [workingdocs/](workingdocs/) |
| `minio` | 26 | third-party MinIO AIStor MCP |
| `infisical` | 7 | third-party Infisical MCP |
| `invoiceninja` | 18 | ✅ [invoice-ninja/](invoice-ninja/) |
| `cloudflare-dns` | 29 | ✅ [cloudflare-dns/](cloudflare-dns/) |
| `transfer` | 5 | ✅ [transfer/](transfer/) |
| `staging` | 4 | ✅ [staging/](staging/) |
| `printblocks` | 19 | ⚠️ source in `/opt/projects/printblocks` on VPS2 — large project, push separately |
| `board` | 9 | ✅ [board/](board/) |
| `miro` | 12 | ✅ [miro/](miro/) |

## WARM (on-demand) — 31 servers

| Server | Tools | Source in this repo |
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
| `githubprojects` | 29 | ⚠️ source not yet extracted |
| `googleworkspace` | 85 | ⚠️ source not yet extracted |
| `grafana` | 44 | third-party `grafana/mcp-grafana` |
| `instantly` | 38 | third-party `instantly-mcp` |
| `linkedin` | 16 | ✅ [linkedin/](linkedin/) |
| `loki` | 6 | ⚠️ source not yet extracted |
| `mail` | 5 | ⚠️ source not yet extracted |
| `n8n` | 29 | ⚠️ source not yet extracted |
| `notion` | 22 | third-party + ✅ [notion-proxy/](notion-proxy/) (description sanitizer) |
| `postgresql` | 1 | third-party `server-postgres` |
| `prometheus` | 6 | third-party `prometheus-mcp-server` |
| `puppeteer` | 7 | third-party `mcp-server-puppeteer` |
| `qdrant` | 2 | ⚠️ source not yet extracted |
| `recraft` | 9 | third-party `@recraft-ai/mcp-recraft-server` |
| `sequentialthinking` | 1 | third-party `server-sequential-thinking` |
| `sqlite` | 6 | third-party `mcp-server-sqlite` |
| `telegram` | 7 | ⚠️ source not yet extracted |
| `telegram-bot` | 6 | ⚠️ source not yet extracted |
| `time` | 2 | third-party `mcp-server-time` |
| `uptime-kuma` | 7 | third-party `mcp-uptime-kuma` |
| `youtube` | 6 | third-party `mcp-youtube` |

## Remaining to extract

These are custom-built servers whose source wasn't found via filesystem search — likely inside Docker image layers or built elsewhere. Need `docker exec <container> cat /app/server.py` to retrieve:

`printblocks` (19 tools — large, at `/opt/projects/printblocks` on VPS2), `githubprojects`, `googleworkspace`, `loki`, `mail`, `n8n`, `qdrant`, `telegram`, `telegram-bot`
