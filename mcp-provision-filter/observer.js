// observer.js — Observer hook for Helix Cortex
// Passively logs every tool call to Helix's Observer API.
// Also compiles per-exchange observations and auto-routes intelligence.
// Fire-and-forget: never blocks or slows the main pipeline.

const HELIX_URL = process.env.HELIX_URL || 'http://helix-cortex:9050';
const OBSERVER_LOG_URL = `${HELIX_URL}/api/v1/observer/log`;
const OBSERVER_BATCH_URL = `${HELIX_URL}/api/v1/observer/log/batch`;
const OBSERVER_WEBHOOK_URL = `${HELIX_URL}/api/v1/observer/webhook`;
const EXCHANGE_POST_URL = `${HELIX_URL}/api/v1/exchange/post`;
const OBSERVER_TIMEOUT_MS = 3000;

// === Action buffer (existing: flush tool calls to observer) ===
let actionBuffer = [];
let flushTimer = null;
const FLUSH_INTERVAL_MS = 5000;
const FLUSH_THRESHOLD = 10;

// === Exchange buffer (NEW: compile exchanges from tool call batches) ===
let exchangeBuffer = [];        // Accumulates tool calls for current exchange
let exchangeTimer = null;        // Fires when exchange boundary detected
let exchangeCounter = 0;         // Sequential exchange number
let lastToolCallTime = 0;        // Track activity
const EXCHANGE_GAP_MS = 30000;   // 30s silence = exchange boundary
const MIN_EXCHANGE_TOOLS = 1;    // Need at least 1 tool call to compile

// Per-session sequence counters
const sessionSequences = new Map();
let currentSessionId = null;

function getSequenceNum(sessionId) {
  if (!sessionId) return 0;
  const current = sessionSequences.get(sessionId) || 0;
  sessionSequences.set(sessionId, current + 1);
  if (sessionSequences.size > 200) {
    const first = sessionSequences.keys().next().value;
    sessionSequences.delete(first);
  }
  return current + 1;
}

function classifyTool(toolName) {
  const name = toolName.toLowerCase();
  if (name.includes('write_file') || name.includes('workspace_write') || name.includes('file_write')) return 'code_write';
  if (name.includes('ssh_execute') || name.includes('execute')) return 'shell_command';
  if (name.includes('cloudflare') || name.includes('dns')) return 'dns_config';
  if (name.includes('infisical') || name.includes('secret')) return 'secrets_config';
  if (name.includes('git_') || name.includes('github')) return 'version_control';
  if (name.includes('docker') || name.includes('compose')) return 'container_ops';
  if (name.includes('kb_') || name.includes('knowledgebase')) return 'knowledge_base';
  if (name.includes('workdocs') || name.includes('workingdocs')) return 'documentation';
  if (name.includes('printblocks') || name.includes('forge') || name.includes('pb_')) return 'pattern_ops';
  if (name.includes('memory') || name.includes('context')) return 'memory_ops';
  if (name.includes('search_tools') || name.includes('list_all_tools')) return 'tool_discovery';
  if (name.includes('search') || name.includes('read') || name.includes('query')) return 'search';
  return 'other';
}

function extractServerName(toolName) {
  const parts = toolName.split('__');
  return parts.length > 1 ? parts[0] : null;
}

// ============================================================
// Tool call observation (existing)
// ============================================================

export function observeToolCall(toolName, args, sessionId, startTime) {
  try {
    if (sessionId) currentSessionId = sessionId;
    lastToolCallTime = Date.now();
    const duration = startTime ? Date.now() - startTime : null;
    
    const action = {
      timestamp: new Date().toISOString(),
      session_id: sessionId || null,
      sequence_num: getSequenceNum(sessionId),
      tool_name: toolName,
      server_name: extractServerName(toolName),
      category: classifyTool(toolName),
      arguments: args || {},
      duration_ms: duration,
      error: false
    };

    // Capture file content from write operations
    if (toolName.toLowerCase().includes('write_file') && args) {
      action.has_file_content = !!(args.content || args.file_content);
      action.file_path = args.path || args.file_path || null;
      if (args.content) action.file_content = args.content;
      if (args.file_content) action.file_content = args.file_content;
    }

    actionBuffer.push(action);
    exchangeBuffer.push(action);  // Also accumulate for exchange

    // Reset exchange boundary timer
    if (exchangeTimer) clearTimeout(exchangeTimer);
    exchangeTimer = setTimeout(compileExchange, EXCHANGE_GAP_MS);

    if (actionBuffer.length >= FLUSH_THRESHOLD) {
      flushBuffer();
    } else if (!flushTimer) {
      flushTimer = setTimeout(flushBuffer, FLUSH_INTERVAL_MS);
    }
  } catch (e) {
    console.log('[Observer] Error building action (non-fatal):', e.message);
  }
}

export function observeToolError(toolName, args, sessionId, error) {
  try {
    if (sessionId) currentSessionId = sessionId;
    lastToolCallTime = Date.now();
    
    const action = {
      timestamp: new Date().toISOString(),
      session_id: sessionId || null,
      sequence_num: getSequenceNum(sessionId),
      tool_name: toolName,
      server_name: extractServerName(toolName),
      category: classifyTool(toolName),
      arguments: args || {},
      result_summary: `Error: ${error?.message || 'unknown'}`,
      error: true
    };
    
    actionBuffer.push(action);
    exchangeBuffer.push(action);  // Also accumulate for exchange
    
    if (exchangeTimer) clearTimeout(exchangeTimer);
    exchangeTimer = setTimeout(compileExchange, EXCHANGE_GAP_MS);
    
    if (actionBuffer.length >= FLUSH_THRESHOLD) flushBuffer();
  } catch (e) {
    // Silent
  }
}

// ============================================================
// Exchange compiler (NEW)
// ============================================================

function compileExchange() {
  exchangeTimer = null;
  if (exchangeBuffer.length < MIN_EXCHANGE_TOOLS) {
    exchangeBuffer = [];
    return;
  }

  const batch = exchangeBuffer.splice(0);
  exchangeCounter++;
  
  try {
    // Extract quantitative data from tool calls
    const toolNames = batch.map(a => a.tool_name);
    const uniqueTools = [...new Set(toolNames)];
    const categories = batch.map(a => a.category);
    const errors = batch.filter(a => a.error);
    
    // Files changed: extract from write tool arguments
    const filesChanged = new Set();
    const servicesChanged = new Set();
    
    for (const action of batch) {
      const args = action.arguments || {};
      const name = (action.tool_name || '').toLowerCase();
      
      // File writes
      if (name.includes('write') || name.includes('create')) {
        if (args.path) filesChanged.add(args.path);
        if (args.file_path) filesChanged.add(args.file_path);
        if (args.deploy_path) filesChanged.add(args.deploy_path);
      }
      
      // SSH commands that touch files or services
      if (name.includes('ssh_execute') && args.command) {
        const cmd = args.command;
        // Docker restarts/rebuilds
        const dockerMatch = cmd.match(/docker\s+(?:restart|compose\s+up|compose\s+build)\s+([\w-]+)/g);
        if (dockerMatch) {
          dockerMatch.forEach(m => {
            const parts = m.split(/\s+/);
            servicesChanged.add(parts[parts.length - 1]);
          });
        }
        // File writes in commands
        const catMatch = cmd.match(/cat\s+>\s+([^\s<]+)/g);
        if (catMatch) {
          catMatch.forEach(m => filesChanged.add(m.replace(/^cat\s+>\s+/, '')));
        }
        const sedMatch = cmd.match(/sed\s+-i[^"]*\s+([^\s]+)$/gm);
        if (sedMatch) {
          sedMatch.forEach(m => {
            const parts = m.trim().split(/\s+/);
            filesChanged.add(parts[parts.length - 1]);
          });
        }
      }
    }
    
    // Determine exchange type from dominant category
    const catCounts = {};
    categories.forEach(c => { catCounts[c] = (catCounts[c] || 0) + 1; });
    const dominant = Object.entries(catCounts).sort((a, b) => b[1] - a[1])[0]?.[0] || 'other';
    const typeMap = {
      'shell_command': 'build', 'code_write': 'build', 'container_ops': 'deploy',
      'dns_config': 'deploy', 'secrets_config': 'deploy',
      'search': 'research', 'tool_discovery': 'research',
      'knowledge_base': 'research', 'documentation': 'review',
      'version_control': 'build', 'pattern_ops': 'build'
    };
    const exchangeType = typeMap[dominant] || 'discuss';
    
    // Complexity from tool count
    const complexity = batch.length <= 3 ? 'low' : batch.length <= 10 ? 'medium' : 'high';
    
    // Auto-generate what_happened
    const toolSummary = Object.entries(
      toolNames.reduce((acc, t) => { acc[t] = (acc[t] || 0) + 1; return acc; }, {})
    ).map(([t, c]) => `${c}x ${t.split('__').pop()}`).join(', ');
    
    const whatHappened = `${batch.length} tool calls (${toolSummary}).` +
      (filesChanged.size > 0 ? ` Files: ${[...filesChanged].slice(0, 5).join(', ')}.` : '') +
      (servicesChanged.size > 0 ? ` Services: ${[...servicesChanged].join(', ')}.` : '') +
      (errors.length > 0 ? ` ${errors.length} error(s).` : '');
    
    // Determine project from file paths
    let project = '';
    for (const f of filesChanged) {
      const match = f.match(/\/opt\/projects\/([a-z][a-z0-9-]+)/);
      if (match) { project = match[1]; break; }
    }
    
    // Build exchange POST
    const exchange = {
      session_id: currentSessionId || 'auto-observer',
      exchange_num: exchangeCounter,
      exchange_type: exchangeType,
      project: project,
      domain: ['deploy', 'build'].includes(exchangeType) ? 'infra' : 
              exchangeType === 'research' ? 'code' : '',
      what_happened: whatHappened,
      files_changed: [...filesChanged],
      services_changed: [...servicesChanged],
      tool_calls: batch.length,
      tools_used: uniqueTools,
      complexity: complexity,
      confidence: errors.length === 0 ? 0.8 : 0.5,
      // Qualitative fields left empty — filled by Mitochondria worker
      decision: '',
      reason: '',
      failure: errors.length > 0 ? errors.map(e => e.result_summary || 'unknown error').join('; ') : '',
      pattern: '',
      constraint_discovered: '',
      notes: `Auto-compiled from observer. ${batch.length} actions over ${((batch[batch.length-1]?.timestamp ? new Date(batch[batch.length-1].timestamp) : new Date()) - (batch[0]?.timestamp ? new Date(batch[0].timestamp) : new Date())) / 1000}s.`,
    };
    
    // Fire-and-forget POST to exchange endpoint
    postExchange(exchange);
    console.log(`[Observer] Exchange #${exchangeCounter} compiled: ${batch.length} tools, ${filesChanged.size} files, ${servicesChanged.size} services, type=${exchangeType}`);
  } catch (e) {
    console.log('[Observer] Exchange compile failed (non-fatal):', e.message);
  }
}

async function postExchange(exchange) {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), OBSERVER_TIMEOUT_MS);
    
    const resp = await fetch(EXCHANGE_POST_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(exchange),
      signal: controller.signal
    });
    
    clearTimeout(timeout);
    const data = await resp.json();
    console.log(`[Observer] Exchange #${exchange.exchange_num} posted:`, JSON.stringify(data).slice(0, 200));
  } catch (e) {
    console.log(`[Observer] Exchange POST failed (non-fatal): ${e.message}`);
  }
}

// ============================================================
// Helix webhook forwarding (existing)
// ============================================================

export async function forwardToHelix(content, filePath, source, contentType) {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), OBSERVER_TIMEOUT_MS);

    await fetch(OBSERVER_WEBHOOK_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        source: source || 'provision-filter',
        content_type: contentType || null,
        content: content,
        file_path: filePath || '',
        scan_code: true,
        update_kb: true,
      }),
      signal: controller.signal
    });

    clearTimeout(timeout);
    console.log(`[Observer->Helix] Forwarded ${filePath || 'content'} (${(content?.length || 0)} chars)`);
  } catch (e) {
    console.log(`[Observer->Helix] Forward failed (non-fatal): ${e.message}`);
  }
}

// ============================================================
// Flush buffer (existing)
// ============================================================

async function flushBuffer() {
  if (flushTimer) {
    clearTimeout(flushTimer);
    flushTimer = null;
  }
  if (actionBuffer.length === 0) return;

  const batch = actionBuffer.splice(0);

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), OBSERVER_TIMEOUT_MS);

    if (batch.length === 1) {
      await fetch(OBSERVER_LOG_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(batch[0]),
        signal: controller.signal
      });
    } else {
      await fetch(OBSERVER_BATCH_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ actions: batch }),
        signal: controller.signal
      });
    }

    clearTimeout(timeout);
    console.log(`[Observer] Flushed ${batch.length} action(s) to Helix`);
  } catch (e) {
    console.log(`[Observer] Flush failed (non-fatal, ${batch.length} actions dropped): ${e.message}`);
  }
}

// Flush on process exit
process.on('beforeExit', () => {
  flushBuffer();
  if (exchangeBuffer.length > 0) compileExchange();
});
