const http = require("http");
const https = require("https");

// Configuration
const ACCESS_TOKEN = process.env.LINKEDIN_ACCESS_TOKEN;
const API_VERSION = "202401";

// LinkedIn URNs
const PERSON_URN = "urn:li:person:xkTotvvy3B";
const ORG_MILLYWEB = "urn:li:organization:110895992";
const ORG_REVENUEFIRST = "urn:li:organization:110955902";

// =============================================================================
// TOOL DEFINITIONS
// =============================================================================
const TOOLS = [
  // --- POSTING ---
  {
    name: "post_to_personal",
    description: "Create a post on Ryan Milly's personal LinkedIn profile",
    inputSchema: {
      type: "object",
      properties: {
        content: { type: "string", description: "Post content (max 3000 chars)" }
      },
      required: ["content"]
    }
  },
  {
    name: "post_to_millyweb",
    description: "Create a post on Millyweb Development company page",
    inputSchema: {
      type: "object",
      properties: {
        content: { type: "string", description: "Post content (max 3000 chars)" }
      },
      required: ["content"]
    }
  },
  {
    name: "post_to_revenuefirst",
    description: "Create a post on RevenueFirst.AI company page",
    inputSchema: {
      type: "object",
      properties: {
        content: { type: "string", description: "Post content (max 3000 chars)" }
      },
      required: ["content"]
    }
  },
  {
    name: "delete_post",
    description: "Delete a LinkedIn post by its URN",
    inputSchema: {
      type: "object",
      properties: {
        postUrn: { type: "string", description: "Post URN (e.g., urn:li:share:123456 or urn:li:ugcPost:123456)" }
      },
      required: ["postUrn"]
    }
  },
  // --- COMMENTS ---
  {
    name: "add_comment",
    description: "Add a comment to a LinkedIn post",
    inputSchema: {
      type: "object",
      properties: {
        postUrn: { type: "string", description: "URN of the post to comment on" },
        text: { type: "string", description: "Comment text" },
        author: { type: "string", enum: ["personal", "millyweb", "revenuefirst"], description: "Who to comment as (default: personal)" }
      },
      required: ["postUrn", "text"]
    }
  },
  {
    name: "get_comments",
    description: "Get comments on a LinkedIn post",
    inputSchema: {
      type: "object",
      properties: {
        postUrn: { type: "string", description: "URN of the post" }
      },
      required: ["postUrn"]
    }
  },
  {
    name: "delete_comment",
    description: "Delete a comment by its URN",
    inputSchema: {
      type: "object",
      properties: {
        commentUrn: { type: "string", description: "URN of the comment to delete" }
      },
      required: ["commentUrn"]
    }
  },
  // --- REACTIONS ---
  {
    name: "add_reaction",
    description: "Add a reaction (like) to a LinkedIn post",
    inputSchema: {
      type: "object",
      properties: {
        postUrn: { type: "string", description: "URN of the post to react to" },
        reactionType: { type: "string", enum: ["LIKE", "PRAISE", "APPRECIATION", "EMPATHY", "INTEREST", "ENTERTAINMENT"], description: "Type of reaction (default: LIKE)" }
      },
      required: ["postUrn"]
    }
  },
  {
    name: "remove_reaction",
    description: "Remove your reaction from a post",
    inputSchema: {
      type: "object",
      properties: {
        postUrn: { type: "string", description: "URN of the post" }
      },
      required: ["postUrn"]
    }
  },
  // --- ANALYTICS ---
  {
    name: "get_org_followers",
    description: "Get follower statistics for a company page",
    inputSchema: {
      type: "object",
      properties: {
        org: { type: "string", enum: ["millyweb", "revenuefirst"], description: "Which org page" }
      },
      required: ["org"]
    }
  },
  {
    name: "get_org_page_stats",
    description: "Get page statistics (views, unique visitors) for a company page",
    inputSchema: {
      type: "object",
      properties: {
        org: { type: "string", enum: ["millyweb", "revenuefirst"], description: "Which org page" },
        timeRange: { type: "string", enum: ["day", "month"], description: "Time granularity (default: month)" }
      },
      required: ["org"]
    }
  },
  {
    name: "get_post_stats",
    description: "Get engagement statistics for a specific post (impressions, clicks, reactions, comments, shares)",
    inputSchema: {
      type: "object",
      properties: {
        postUrn: { type: "string", description: "URN of the post (share or ugcPost)" }
      },
      required: ["postUrn"]
    }
  },
  // --- PROFILE ---
  {
    name: "get_profile",
    description: "Get the authenticated user's LinkedIn profile info",
    inputSchema: { type: "object", properties: {} }
  },
  {
    name: "get_connection_count",
    description: "Get the number of 1st-degree connections",
    inputSchema: { type: "object", properties: {} }
  },
  // --- ORG POSTS ---
  {
    name: "get_org_posts",
    description: "Get recent posts from a company page",
    inputSchema: {
      type: "object",
      properties: {
        org: { type: "string", enum: ["millyweb", "revenuefirst"], description: "Which org page" },
        count: { type: "number", description: "Number of posts to retrieve (default: 10, max: 100)" }
      },
      required: ["org"]
    }
  },
  // --- INFO ---
  {
    name: "get_linkedin_urns",
    description: "Get the configured LinkedIn URNs for personal profile and company pages",
    inputSchema: { type: "object", properties: {} }
  }
];

// =============================================================================
// HTTP HELPERS
// =============================================================================
function linkedInRequest(method, path, body = null) {
  return new Promise((resolve, reject) => {
    const bodyStr = body ? JSON.stringify(body) : null;
    
    const options = {
      hostname: "api.linkedin.com",
      path: path,
      method: method,
      headers: {
        "Authorization": `Bearer ${ACCESS_TOKEN}`,
        "LinkedIn-Version": API_VERSION,
        "X-Restli-Protocol-Version": "2.0.0"
      }
    };
    
    if (bodyStr) {
      options.headers["Content-Type"] = "application/json";
      options.headers["Content-Length"] = Buffer.byteLength(bodyStr);
    }

    const req = https.request(options, (res) => {
      let data = "";
      res.on("data", chunk => data += chunk);
      res.on("end", () => {
        const result = {
          statusCode: res.statusCode,
          headers: res.headers
        };
        
        if (data) {
          try {
            result.body = JSON.parse(data);
          } catch {
            result.body = data;
          }
        }
        
        resolve(result);
      });
    });

    req.on("error", reject);
    if (bodyStr) req.write(bodyStr);
    req.end();
  });
}
function getOrgUrn(org) {
  return org === "millyweb" ? ORG_MILLYWEB : ORG_REVENUEFIRST;
}

function getAuthorUrn(author) {
  if (!author || author === "personal") return PERSON_URN;
  if (author === "millyweb") return ORG_MILLYWEB;
  if (author === "revenuefirst") return ORG_REVENUEFIRST;
  return PERSON_URN;
}


// =============================================================================
// TOOL IMPLEMENTATIONS
// =============================================================================
async function createPost(author, content) {
  const body = {
    author: author,
    commentary: content,
    visibility: "PUBLIC",
    distribution: {
      feedDistribution: "MAIN_FEED",
      targetEntities: [],
      thirdPartyDistributionChannels: []
    },
    lifecycleState: "PUBLISHED",
    isReshareDisabledByAuthor: false
  };
  
  const res = await linkedInRequest("POST", "/v2/posts", body);
  return {
    success: res.statusCode === 201,
    statusCode: res.statusCode,
    postId: res.headers?.["x-restli-id"] || null,
    message: res.statusCode === 201 ? "Post created successfully" : res.body
  };
}

async function deletePost(postUrn) {
  const encodedUrn = encodeURIComponent(postUrn);
  const res = await linkedInRequest("DELETE", `/v2/posts/${encodedUrn}`);
  return {
    success: res.statusCode === 204,
    statusCode: res.statusCode,
    message: res.statusCode === 204 ? "Post deleted" : res.body
  };
}

async function addComment(postUrn, text, author) {
  const authorUrn = getAuthorUrn(author);
  const body = {
    actor: authorUrn,
    object: postUrn,
    message: { text: text }
  };
  
  const res = await linkedInRequest("POST", "/v2/socialActions/" + encodeURIComponent(postUrn) + "/comments", body);
  return {
    success: res.statusCode === 201,
    statusCode: res.statusCode,
    commentId: res.headers?.["x-restli-id"] || null,
    body: res.body
  };
}

async function getComments(postUrn) {
  const res = await linkedInRequest("GET", `/v2/socialActions/${encodeURIComponent(postUrn)}/comments`);
  return {
    success: res.statusCode === 200,
    statusCode: res.statusCode,
    comments: res.body?.elements || [],
    total: res.body?.paging?.total || 0
  };
}

async function deleteComment(commentUrn) {
  const res = await linkedInRequest("DELETE", `/v2/socialActions/${encodeURIComponent(commentUrn)}`);
  return {
    success: res.statusCode === 204,
    statusCode: res.statusCode
  };
}

async function addReaction(postUrn, reactionType = "LIKE") {
  const body = {
    actor: PERSON_URN,
    reactionType: reactionType
  };
  
  const res = await linkedInRequest("POST", `/v2/socialActions/${encodeURIComponent(postUrn)}/likes`, body);
  return {
    success: res.statusCode === 201,
    statusCode: res.statusCode,
    body: res.body
  };
}

async function removeReaction(postUrn) {
  const res = await linkedInRequest("DELETE", `/v2/socialActions/${encodeURIComponent(postUrn)}/likes/${encodeURIComponent(PERSON_URN)}`);
  return {
    success: res.statusCode === 204,
    statusCode: res.statusCode
  };
}

async function getOrgFollowers(org) {
  const orgUrn = getOrgUrn(org);
  const res = await linkedInRequest("GET", `/v2/organizationalEntityFollowerStatistics?q=organizationalEntity&organizationalEntity=${encodeURIComponent(orgUrn)}`);
  return {
    success: res.statusCode === 200,
    statusCode: res.statusCode,
    data: res.body
  };
}

async function getOrgPageStats(org, timeRange = "month") {
  const orgUrn = getOrgUrn(org);
  const timeGranularity = timeRange === "day" ? "DAY" : "MONTH";
  const res = await linkedInRequest("GET", `/v2/organizationPageStatistics?q=organization&organization=${encodeURIComponent(orgUrn)}&timeIntervals.timeGranularityType=${timeGranularity}&timeIntervals.timeRange.start=0`);
  return {
    success: res.statusCode === 200,
    statusCode: res.statusCode,
    data: res.body
  };
}

async function getPostStats(postUrn) {
  const res = await linkedInRequest("GET", `/v2/socialActions/${encodeURIComponent(postUrn)}`);
  return {
    success: res.statusCode === 200,
    statusCode: res.statusCode,
    data: res.body
  };
}

async function getProfile() {
  const res = await linkedInRequest("GET", "/v2/userinfo");
  return {
    success: res.statusCode === 200,
    statusCode: res.statusCode,
    profile: res.body
  };
}

async function getConnectionCount() {
  const res = await linkedInRequest("GET", `/v2/networkSizes/${encodeURIComponent(PERSON_URN)}?edgeType=FIRST_DEGREE`);
  return {
    success: res.statusCode === 200,
    statusCode: res.statusCode,
    data: res.body
  };
}

async function getOrgPosts(org, count = 10) {
  const orgUrn = getOrgUrn(org);
  const res = await linkedInRequest("GET", `/v2/posts?author=${encodeURIComponent(orgUrn)}&q=author&count=${count}`);
  return {
    success: res.statusCode === 200,
    statusCode: res.statusCode,
    posts: res.body?.elements || [],
    total: res.body?.paging?.total || 0
  };
}


// =============================================================================
// TOOL DISPATCHER
// =============================================================================
async function handleToolCall(name, args) {
  switch (name) {
    case "post_to_personal":
      return await createPost(PERSON_URN, args.content);
    case "post_to_millyweb":
      return await createPost(ORG_MILLYWEB, args.content);
    case "post_to_revenuefirst":
      return await createPost(ORG_REVENUEFIRST, args.content);
    case "delete_post":
      return await deletePost(args.postUrn);
    case "add_comment":
      return await addComment(args.postUrn, args.text, args.author);
    case "get_comments":
      return await getComments(args.postUrn);
    case "delete_comment":
      return await deleteComment(args.commentUrn);
    case "add_reaction":
      return await addReaction(args.postUrn, args.reactionType || "LIKE");
    case "remove_reaction":
      return await removeReaction(args.postUrn);
    case "get_org_followers":
      return await getOrgFollowers(args.org);
    case "get_org_page_stats":
      return await getOrgPageStats(args.org, args.timeRange);
    case "get_post_stats":
      return await getPostStats(args.postUrn);
    case "get_profile":
      return await getProfile();
    case "get_connection_count":
      return await getConnectionCount();
    case "get_org_posts":
      return await getOrgPosts(args.org, args.count || 10);
    case "get_linkedin_urns":
      return {
        personal: PERSON_URN,
        millyweb: ORG_MILLYWEB,
        revenuefirst: ORG_REVENUEFIRST
      };
    default:
      throw new Error(`Unknown tool: ${name}`);
  }
}

// =============================================================================
// MCP SERVER
// =============================================================================
const server = http.createServer(async (req, res) => {
  // Health check
  if (req.url === "/health") {
    res.writeHead(200, { "Content-Type": "application/json" });
    return res.end(JSON.stringify({ 
      status: "healthy", 
      tools: TOOLS.length,
      version: "1.0.0",
      tokenConfigured: !!ACCESS_TOKEN
    }));
  }

  // Only accept POST
  if (req.method !== "POST") {
    res.writeHead(405);
    return res.end();
  }

  let body = "";
  req.on("data", chunk => body += chunk);
  req.on("end", async () => {
    try {
      const request = JSON.parse(body);
      let response;

      switch (request.method) {
        case "initialize":
          response = {
            result: {
              protocolVersion: "2024-11-05",
              capabilities: { tools: {} },
              serverInfo: { name: "mcp-linkedin", version: "1.0.0" }
            }
          };
          break;

        case "tools/list":
          response = { result: { tools: TOOLS } };
          break;

        case "tools/call":
          try {
            const result = await handleToolCall(request.params.name, request.params.arguments || {});
            response = {
              result: {
                content: [{ type: "text", text: JSON.stringify(result, null, 2) }]
              }
            };
          } catch (e) {
            response = {
              result: {
                content: [{ type: "text", text: JSON.stringify({ error: e.message }) }],
                isError: true
              }
            };
          }
          break;

        default:
          response = { error: { code: -32601, message: "Method not found" } };
      }

      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ jsonrpc: "2.0", id: request.id, ...response }));
    } catch (e) {
      res.writeHead(500, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ 
        jsonrpc: "2.0", 
        error: { code: -32603, message: e.message } 
      }));
    }
  });
});

const PORT = process.env.PORT || 8080;
server.listen(PORT, "0.0.0.0", () => {
  console.log(`LinkedIn MCP server running on port ${PORT}`);
  console.log(`Tools available: ${TOOLS.length}`);
  console.log(`Token configured: ${!!ACCESS_TOKEN}`);
});
