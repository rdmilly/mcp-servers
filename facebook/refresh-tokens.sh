#!/bin/bash
# Facebook Page Token Regenerator
# Converts a short-lived user token into permanent page tokens
# Usage: ./refresh-tokens.sh

set -euo pipefail

echo "📱 Facebook Page Token Regenerator"
echo "================================="
echo ""
echo "I need 3 things from you:"
echo ""

# Step 1: Get App credentials
read -p "1. Facebook App ID: " APP_ID
read -p "2. Facebook App Secret: " APP_SECRET
echo ""
echo "3. Go to: https://developers.facebook.com/tools/explorer/"
echo "   - Select your app from dropdown"
echo "   - Click 'Generate Access Token'"
echo "   - Check these permissions:"
echo "     ☐ pages_manage_posts"
echo "     ☐ pages_read_engagement"
echo "     ☐ pages_read_user_content"
echo "     ☐ pages_show_list"
echo "   - Click 'Generate Access Token'"
echo "   - Authorize when prompted"
echo "   - Copy the token"
echo ""
read -p "3. Paste the short-lived user token: " SHORT_TOKEN

echo ""
echo "⏳ Step 1: Exchanging for long-lived user token..."
LONG_RESPONSE=$(curl -s "https://graph.facebook.com/v22.0/oauth/access_token?grant_type=fb_exchange_token&client_id=${APP_ID}&client_secret=${APP_SECRET}&fb_exchange_token=${SHORT_TOKEN}")

LONG_TOKEN=$(echo "$LONG_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null)

if [ -z "$LONG_TOKEN" ]; then
  echo "❌ Failed to get long-lived token!"
  echo "Response: $LONG_RESPONSE"
  exit 1
fi

# Verify it's actually long-lived
TOKEN_INFO=$(curl -s "https://graph.facebook.com/debug_token?input_token=${LONG_TOKEN}&access_token=${APP_ID}|${APP_SECRET}")
EXPIRES=$(echo "$TOKEN_INFO" | python3 -c "import sys,json; print(json.load(sys.stdin).get('data',{}).get('expires_at',0))" 2>/dev/null)
if [ "$EXPIRES" != "0" ] && [ -n "$EXPIRES" ]; then
  EXPIRES_DATE=$(date -d @"$EXPIRES" '+%Y-%m-%d %H:%M' 2>/dev/null || echo "unknown")
  echo "✅ Long-lived user token obtained (expires: $EXPIRES_DATE)"
else
  echo "✅ Long-lived user token obtained (never expires)"
fi

echo ""
echo "⏳ Step 2: Getting page tokens (these will be PERMANENT)..."
PAGES_RESPONSE=$(curl -s "https://graph.facebook.com/v22.0/me/accounts?access_token=${LONG_TOKEN}")

# Parse pages
echo "$PAGES_RESPONSE" | python3 << 'PYEOF'
import json, sys

data = json.load(sys.stdin)
if "error" in data:
    print(f"\n\u274c Error: {data['error']['message']}")
    sys.exit(1)

pages = data.get("data", [])
if not pages:
    print("\n\u274c No pages found! Make sure you have admin access to Facebook Pages.")
    sys.exit(1)

print(f"\n\u2705 Found {len(pages)} pages:\n")

# Map page IDs to our env var names
PAGE_MAP = {
    "947949231746181": "FB_PAGE_TOKEN_RYAN_MILLY",
    "965535289969570": "FB_PAGE_TOKEN_REVENUEFIRST",
    "843420718864542": "FB_PAGE_TOKEN_MILLYWEB",
    "931864703343950": "FB_PAGE_TOKEN_VIBE_JOURNEY",
    "103779354796764": "FB_PAGE_TOKEN_MOVING_PDX",
}

env_lines = []
env_lines.append("# Facebook Page Tokens (Permanent - derived from long-lived user token)")
env_lines.append(f"# Generated: {__import__('datetime').datetime.now().strftime('%B %d, %Y')}")
env_lines.append("")

matched = 0
for page in pages:
    pid = page["id"]
    name = page["name"]
    token = page["access_token"]
    env_var = PAGE_MAP.get(pid, f"FB_PAGE_TOKEN_{name.upper().replace(' ','_').replace('.','_')}")
    
    status = "\u2705 MATCHED" if pid in PAGE_MAP else "\u2753 NEW (not in current config)"
    print(f"  {status}: {name} (ID: {pid})")
    
    if pid in PAGE_MAP:
        matched += 1
        env_lines.append(f"# {name} - ID: {pid}")
        env_lines.append(f"{env_var}={token}")
        env_lines.append("")

print(f"\nMatched {matched}/5 configured pages")

if matched > 0:
    env_content = "\n".join(env_lines)
    with open("/opt/stacks/mcp-facebook/.env.new", "w") as f:
        f.write(env_content + "\n")
    print(f"\n\u2705 New .env written to /opt/stacks/mcp-facebook/.env.new")
    print("Review it, then run:")
    print("  cp /opt/stacks/mcp-facebook/.env.new /opt/stacks/mcp-facebook/.env")
    print("  cd /opt/stacks/mcp-facebook && docker compose down && docker compose up -d")
PYEOF

echo ""
echo "Done! Review the .env.new file, then apply it."
