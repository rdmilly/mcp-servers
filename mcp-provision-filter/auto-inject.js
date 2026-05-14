// auto-inject.js — Helix slim index injection
// Injects a compact page index (~100-150 tokens) instead of the full runbook.
// Claude fetches full page content on-demand when triggers match.
// Updated: 2026-03-03

const HELIX_URL = process.env.HELIX_URL || 'http://helix-cortex:9050';
const FETCH_TIMEOUT_MS = 5000;

// SSE: inject once per session
const injectedSessions = new Set();
// JSON-RPC: 5-minute cooldown
const COOLDOWN_MS = 5 * 60 * 1000;
let lastJsonRpcInjection = 0;

async function fetchIndex() {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
    const resp = await fetch(
      `${HELIX_URL}/api/v1/runbook/index`,
      { signal: controller.signal }
    );
    clearTimeout(timeout);
    if (!resp.ok) {
      // Fallback to old runbook if new endpoint not available yet
      console.log('[AutoInject] Index endpoint not ready, trying legacy runbook');
      const fallback = await fetch(
        `${HELIX_URL}/api/v1/inject/runbook?sections=alerts,handoff,waiting`,
        { signal: AbortSignal.timeout(FETCH_TIMEOUT_MS) }
      );
      if (!fallback.ok) return null;
      const fb = await fallback.json();
      return fb.text || null;
    }
    const data = await resp.json();
    return data.text || null;
  } catch (e) {
    console.log('[AutoInject] Index fetch failed (non-fatal):', e.message);
    return null;
  }
}

export async function maybeInjectContext(sessionId, toolResult) {
  let shouldInject = false;

  if (sessionId) {
    if (!injectedSessions.has(sessionId)) {
      shouldInject = true;
      injectedSessions.add(sessionId);
      if (injectedSessions.size > 100) {
        const first = injectedSessions.values().next().value;
        injectedSessions.delete(first);
      }
    }
  } else {
    const now = Date.now();
    if (now - lastJsonRpcInjection > COOLDOWN_MS) {
      shouldInject = true;
      lastJsonRpcInjection = now;
    }
  }

  if (!shouldInject) return toolResult;

  const index = await fetchIndex();
  if (!index) return toolResult;

  console.log(`[AutoInject] Injected index (${index.length} chars) for session ${sessionId || 'jsonrpc'}`);

  if (toolResult && toolResult.content && Array.isArray(toolResult.content)) {
    toolResult.content.unshift({ type: 'text', text: index });
  }

  return toolResult;
}

export function markNewSession() {}
