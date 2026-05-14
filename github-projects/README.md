# github-projects MCP server

GitHub Projects v2 MCP server. TypeScript, uses GitHub GraphQL API. Full source is a multi-file TypeScript project.

## Tools (29)

**Projects:** list_projects, list_org_projects, list_user_projects, get_project, get_project_columns, get_project_fields, get_project_items, create_project, update_project, delete_project, copy_project, mark_as_template, unmark_as_template

**Project items:** add_item_by_id, add_draft_issue, update_item_field_value, bulk_update_item_field_value, clear_item_field_value, archive_item, unarchive_item, delete_item, update_item_position

**Fields:** create_field, update_field, delete_field, update_status_update

**Issues:** get_issue, list_issues, create_issue, update_issue

**Repos:** get_repository, list_repositories (via repository operations)

## Config

| Env var | Value |
|---|---|
| `GITHUB_OWNER` | `rdmilly` |
| `GITHUB_OWNER_TYPE` | `user` |
| `GITHUB_TOKEN` | injected by provisioner |

## Source

Full TypeScript source at `/opt/projects/mw-mcp-servers/mcp-github-projects/` on VPS2:
- `src/index.ts` — MCP server entry point, tool registration
- `src/operations/projects.ts` — all Projects v2 GraphQL operations
- `src/operations/issues.ts` — issue operations
- `src/operations/repositories.ts` — repo operations
- `src/graphql/` — all `.graphql` query files
- `src/common/` — utils, errors

Built with `bun build` to `/app/build/index.js`. Run via supergateway wrapping stdio.
