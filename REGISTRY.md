# Server Registry

All 48 servers managed by [mcp-provisioner](https://github.com/rdmilly/mcp-provisioner). Source in this repo = custom-built code. Everything else runs a third-party package via provisioner manifest.

## HOT (always running) — 17 servers

| Server | Tools | Source |
|---|---|---|
| `helix` | 33 | [rdmilly/helix](https://github.com/rdmilly/helix) repo |
| `docker` | 18 | third-party `mcp-server-docker` |
| `filesystem` | 14 | third-party `server-filesystem` |
| `github` | 26 | third-party `mcp-server-github` |
| `slack` | 8 | third-party `server-slack` |
| `gateway` | 9 | [gateway/](gateway/) — archived (replaced by Lifeline) |
| `knowledgebase` | 4 | custom `mcp-kb-gateway` |
| `workingdocs` | 5 | custom `mcp-workdocs` |
| `minio` | 26 | third-party MinIO AIStor MCP |
| `infisical` | 7 | third-party Infisical MCP |
| `invoiceninja` | 18 | [invoice-ninja/](invoice-ninja/) |
| `cloudflare-dns` | 29 | custom cloudflare-dns server |
| `transfer` | 5 | custom mcp-transfer |
| `staging` | 4 | custom mcp-staging |
| `printblocks` | 19 | custom printblocks |
| `board` | 9 | custom mcp-board |
| `miro` | 12 | third-party Miro MCP |

## WARM (on-demand) — 31 servers

| Server | Tools | Source |
|---|---|---|
| `bravesearch` | 2 | third-party `server-brave-search` |
| `browserless` | 5 | [browserless/](browserless/) |
| `cloudflare` | 89 | third-party `@cloudflare/mcp-server-cloudflare` |
| `context7` | 2 | third-party `@upstash/context7-mcp` |
| `docker-readonly` | 19 | third-party `mcp-server-docker` (read-only) |
| `everything` | 13 | third-party `server-everything` |
| `facebook` | 11 | [facebook/](facebook/) |
| `fetch` | 1 | third-party `mcp-server-fetch` |
| `filetransfer` | 6 | [filetransfer/](filetransfer/) |
| `git` | 12 | third-party `mcp-server-git` |
| `githubprojects` | 29 | custom `mcp-github-projects` |
| `googleworkspace` | 85 | custom `mcp-google-workspace` |
| `grafana` | 44 | third-party `grafana/mcp-grafana` |
| `instantly` | 38 | third-party `instantly-mcp` |
| `linkedin` | 16 | [linkedin/](linkedin/) |
| `loki` | 6 | custom `mcp-loki` |
| `mail` | 5 | custom `mcp-mail` |
| `n8n` | 29 | custom `mcp-n8n` |
| `notion` | 22 | third-party `@notionhq/notion-mcp-server` (via notion-proxy) |
| `postgresql` | 1 | third-party `server-postgres` |
| `prometheus` | 6 | third-party `prometheus-mcp-server` |
| `puppeteer` | 7 | third-party `mcp-server-puppeteer` |
| `qdrant` | 2 | custom `mcp-qdrant` |
| `recraft` | 9 | third-party `@recraft-ai/mcp-recraft-server` |
| `sequentialthinking` | 1 | third-party `server-sequential-thinking` |
| `sqlite` | 6 | third-party `mcp-server-sqlite` |
| `telegram` | 7 | custom `mcp-telegram` |
| `telegram-bot` | 6 | custom `mcp-telegram-bot` |
| `time` | 2 | third-party `mcp-server-time` |
| `uptime-kuma` | 7 | third-party `mcp-uptime-kuma` |
| `youtube` | 6 | third-party `mcp-youtube` |

**Total: 48 servers, ~740 tools**

The provisioner manifest at `/opt/projects/mcp-provisioner/config/manifest.json` on VPS2 is the authoritative source for container specs, ports, secrets, and tool definitions.
