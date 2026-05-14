const http = require("http");
const https = require("https");

const GRAPH_API_VERSION = "v22.0";

const PAGES = {
  ryan_milly: { id: "947949231746181", name: "Ryan Milly", token: process.env.FB_PAGE_TOKEN_RYAN_MILLY },
  revenuefirst: { id: "965535289969570", name: "RevenueFirst.AI", token: process.env.FB_PAGE_TOKEN_REVENUEFIRST },
  millyweb: { id: "843420718864542", name: "Millyweb Development", token: process.env.FB_PAGE_TOKEN_MILLYWEB },
  vibe_journey: { id: "931864703343950", name: "The Vibe Journey", token: process.env.FB_PAGE_TOKEN_VIBE_JOURNEY },
  moving_pdx: { id: "103779354796764", name: "Moving PDX", token: process.env.FB_PAGE_TOKEN_MOVING_PDX }
};

const TOOLS = [
  { name: "post_to_page", description: "Create a post on a Facebook Page", inputSchema: { type: "object", properties: { page: { type: "string", enum: ["ryan_milly", "revenuefirst", "millyweb", "vibe_journey", "moving_pdx"] }, message: { type: "string" }, link: { type: "string" } }, required: ["page", "message"] } },
  { name: "post_photo", description: "Post a photo to a Facebook Page", inputSchema: { type: "object", properties: { page: { type: "string", enum: ["ryan_milly", "revenuefirst", "millyweb", "vibe_journey", "moving_pdx"] }, photo_url: { type: "string" }, caption: { type: "string" } }, required: ["page", "photo_url"] } },
  { name: "delete_post", description: "Delete a Facebook post", inputSchema: { type: "object", properties: { post_id: { type: "string" }, page: { type: "string", enum: ["ryan_milly", "revenuefirst", "millyweb", "vibe_journey", "moving_pdx"] } }, required: ["post_id", "page"] } },
  { name: "get_page_info", description: "Get Facebook Page info", inputSchema: { type: "object", properties: { page: { type: "string", enum: ["ryan_milly", "revenuefirst", "millyweb", "vibe_journey", "moving_pdx"] } }, required: ["page"] } },
  { name: "get_page_posts", description: "Get recent posts from a Facebook Page", inputSchema: { type: "object", properties: { page: { type: "string", enum: ["ryan_milly", "revenuefirst", "millyweb", "vibe_journey", "moving_pdx"] }, limit: { type: "number" } }, required: ["page"] } },
  { name: "get_page_insights", description: "Get page analytics", inputSchema: { type: "object", properties: { page: { type: "string", enum: ["ryan_milly", "revenuefirst", "millyweb", "vibe_journey", "moving_pdx"] }, period: { type: "string", enum: ["day", "week", "days_28"] } }, required: ["page"] } },
  { name: "get_post_insights", description: "Get post analytics", inputSchema: { type: "object", properties: { post_id: { type: "string" }, page: { type: "string", enum: ["ryan_milly", "revenuefirst", "millyweb", "vibe_journey", "moving_pdx"] } }, required: ["post_id", "page"] } },
  { name: "get_post_comments", description: "Get comments on a post", inputSchema: { type: "object", properties: { post_id: { type: "string" }, page: { type: "string", enum: ["ryan_milly", "revenuefirst", "millyweb", "vibe_journey", "moving_pdx"] }, limit: { type: "number" } }, required: ["post_id", "page"] } },
  { name: "reply_to_comment", description: "Reply to a comment", inputSchema: { type: "object", properties: { comment_id: { type: "string" }, message: { type: "string" }, page: { type: "string", enum: ["ryan_milly", "revenuefirst", "millyweb", "vibe_journey", "moving_pdx"] } }, required: ["comment_id", "message", "page"] } },
  { name: "list_pages", description: "List configured Facebook pages", inputSchema: { type: "object", properties: {} } },
  { name: "verify_token", description: "Verify page token validity", inputSchema: { type: "object", properties: { page: { type: "string", enum: ["ryan_milly", "revenuefirst", "millyweb", "vibe_journey", "moving_pdx"] } }, required: ["page"] } }
];

function graphRequest(method, path, token, body = null) {
  return new Promise((resolve, reject) => {
    const url = new URL(`https://graph.facebook.com/${GRAPH_API_VERSION}${path}`);
    if (method === "GET") url.searchParams.set("access_token", token);
    const options = { hostname: url.hostname, path: url.pathname + url.search, method, headers: {} };
    let bodyStr = null;
    if (body) {
      body.access_token = token;
      bodyStr = new URLSearchParams(body).toString();
      options.headers["Content-Type"] = "application/x-www-form-urlencoded";
      options.headers["Content-Length"] = Buffer.byteLength(bodyStr);
    }
    const req = https.request(options, (res) => {
      let data = "";
      res.on("data", chunk => data += chunk);
      res.on("end", () => {
        const result = { statusCode: res.statusCode };
        try { result.body = JSON.parse(data); } catch { result.body = data; }
        resolve(result);
      });
    });
    req.on("error", reject);
    if (bodyStr) req.write(bodyStr);
    req.end();
  });
}

function getPage(k) {
  const p = PAGES[k];
  if (!p) throw new Error(`Unknown page: ${k}`);
  if (!p.token) throw new Error(`No token for: ${k}`);
  return p;
}

async function handleToolCall(name, args) {
  const page = args.page ? getPage(args.page) : null;
  switch (name) {
    case "post_to_page": {
      const body = { message: args.message };
      if (args.link) body.link = args.link;
      const r = await graphRequest("POST", `/${page.id}/feed`, page.token, body);
      return { success: r.statusCode === 200, postId: r.body?.id, page: page.name, message: r.statusCode === 200 ? "Post created" : r.body?.error?.message };
    }
    case "post_photo": {
      const body = { url: args.photo_url };
      if (args.caption) body.caption = args.caption;
      const r = await graphRequest("POST", `/${page.id}/photos`, page.token, body);
      return { success: r.statusCode === 200, photoId: r.body?.id, postId: r.body?.post_id, page: page.name };
    }
    case "delete_post": {
      const r = await graphRequest("DELETE", `/${args.post_id}`, page.token);
      return { success: r.statusCode === 200 && r.body?.success === true };
    }
    case "get_page_info": {
      const r = await graphRequest("GET", `/${page.id}?fields=id,name,about,category,fan_count,followers_count,link,website,picture`, page.token);
      return { success: r.statusCode === 200, page: r.body };
    }
    case "get_page_posts": {
      const r = await graphRequest("GET", `/${page.id}/posts?fields=id,message,created_time,permalink_url,shares,reactions.summary(true),comments.summary(true)&limit=${args.limit || 10}`, page.token);
      return { success: r.statusCode === 200, posts: r.body?.data || [] };
    }
    case "get_page_insights": {
      const r = await graphRequest("GET", `/${page.id}/insights?metric=page_impressions,page_impressions_unique,page_engaged_users,page_post_engagements,page_fans&period=${args.period || "day"}`, page.token);
      return { success: r.statusCode === 200, insights: r.body?.data || [], error: r.body?.error?.message };
    }
    case "get_post_insights": {
      const r = await graphRequest("GET", `/${args.post_id}/insights?metric=post_impressions,post_impressions_unique,post_engaged_users,post_clicks,post_reactions_by_type_total`, page.token);
      return { success: r.statusCode === 200, insights: r.body?.data || [] };
    }
    case "get_post_comments": {
      const r = await graphRequest("GET", `/${args.post_id}/comments?fields=id,message,from,created_time,like_count&limit=${args.limit || 25}`, page.token);
      return { success: r.statusCode === 200, comments: r.body?.data || [] };
    }
    case "reply_to_comment": {
      const r = await graphRequest("POST", `/${args.comment_id}/comments`, page.token, { message: args.message });
      return { success: r.statusCode === 200, replyId: r.body?.id };
    }
    case "list_pages":
      return Object.fromEntries(Object.entries(PAGES).map(([k, p]) => [k, { id: p.id, name: p.name, tokenConfigured: !!p.token }]));
    case "verify_token": {
      const r = await graphRequest("GET", "/debug_token?input_token=" + page.token, page.token);
      return { valid: r.body?.data?.is_valid || false, expiresAt: r.body?.data?.expires_at, scopes: r.body?.data?.scopes || [] };
    }
    default: throw new Error(`Unknown tool: ${name}`);
  }
}

const server = http.createServer(async (req, res) => {
  if (req.url === "/health") {
    res.writeHead(200, { "Content-Type": "application/json" });
    return res.end(JSON.stringify({ status: "healthy", tools: TOOLS.length, configuredPages: Object.values(PAGES).filter(p => p.token).length }));
  }
  if (req.method !== "POST" || (req.url !== "/" && req.url !== "/mcp")) {
    res.writeHead(405);
    return res.end();
  }
  let body = "";
  req.on("data", c => body += c);
  req.on("end", async () => {
    try {
      const rq = JSON.parse(body);
      let response;
      switch (rq.method) {
        case "initialize":
          response = { result: { protocolVersion: "2024-11-05", capabilities: { tools: {} }, serverInfo: { name: "mcp-facebook", version: "1.0.0" } } };
          break;
        case "tools/list":
          response = { result: { tools: TOOLS } };
          break;
        case "tools/call":
          try {
            const result = await handleToolCall(rq.params.name, rq.params.arguments || {});
            response = { result: { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] } };
          } catch (e) {
            response = { result: { content: [{ type: "text", text: JSON.stringify({ error: e.message }) }], isError: true } };
          }
          break;
        default:
          response = { error: { code: -32601, message: "Method not found" } };
      }
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ jsonrpc: "2.0", id: rq.id, ...response }));
    } catch (e) {
      res.writeHead(500, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ jsonrpc: "2.0", error: { code: -32603, message: e.message } }));
    }
  });
});

server.listen(process.env.PORT || 8080, "0.0.0.0", () => console.log("Facebook MCP running"));
