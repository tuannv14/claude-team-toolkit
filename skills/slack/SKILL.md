---
name: slack
description: Use when posting Slack messages/threads, uploading files, fetching channel history, or sending deploy/incident alerts. Multi-workspace via SLACK_PROFILE.
user-invocable: true
allowed-tools:
  - Read
  - Bash
---

# /slack — Slack Web API (multi-workspace)

REST against `https://slack.com/api/`. Bearer auth with bot/user OAuth token.
Profiles isolate workspaces.

Arguments: `$ARGUMENTS`. Profile resolution: `--profile <name>` → `SLACK_PROFILE` → `~/.slack/active_profile` → `[default]`.

## Overview

REST against Slack Web API with bot OAuth tokens. Profiles isolate workspaces. Default to bot tokens (`xoxb-`) — never use user tokens (`xoxp-`) which carry the user's full permissions.

## When to Use

- Posting deploy / incident alerts to channels
- Threaded replies to existing messages (incident timelines)
- Block Kit rich messages (status dashboards, deploy summaries)
- File uploads (logs, screenshots) for incident triage
- Fetching channel history for context

## When NOT to Use

- Real-time event consumption → use Events API + your own server, not REST
- Slash command handlers → that's an HTTP webhook, not API client
- Complex workflows → Slack Workflow Builder or Bolt SDK
- Direct messages to users at scale → looks spammy, against TOS

## Dependencies

`curl`, `jq`.

## Profile config

`~/.slack/credentials` (mode 600):

```ini
[default]
bot_token = xoxb-xxxxxxxxxxxx-xxxxxxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxx
default_channel = #general

[work]
bot_token = xoxb-xxxxxxxxxxxx-xxxxxxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxx
default_channel = #engineering
# require confirmation for any post (e.g., for sensitive workspaces)
require_confirm = true

[client_a]
bot_token = xoxb-xxxxxxxxxxxx-xxxxxxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxx
default_channel = #project-a
```

**Get a bot token:**

1. https://api.slack.com/apps → Create New App → From scratch
2. OAuth & Permissions → add bot scopes (least privilege):
   - `chat:write` — post messages
   - `channels:read` — list channels
   - `users:read` — resolve user names
   - `files:write` — upload files
3. Install to Workspace → copy "Bot User OAuth Token" (starts with `xoxb-`)
4. Invite the bot to channels you want it to post in: `/invite @YourBot`

**Never use `xoxp-` user tokens** unless absolutely necessary — they have
the user's full permissions and are riskier if leaked.

## Helpers

> Shared profile/INI/`ctt_*` pattern reference: [profiles-and-credentials](../profiles-and-credentials/SKILL.md).

```bash
source "$HOME/.claude-team-toolkit/lib/credentials.sh"
source "$HOME/.claude-team-toolkit/lib/confirm.sh"
ctt_load_creds slack "$PROFILE"

slack_api() {
  local method="$1" path="$2"; shift 2
  curl -s -X "$method" \
    -H "Authorization: Bearer $CTT_BOT_TOKEN" \
    -H "Content-Type: application/json; charset=utf-8" \
    "$@" \
    "https://slack.com/api/$path"
}
```

## Dispatch

### `post <channel> <message>` — post a message

```bash
CHANNEL="${1:-$CTT_DEFAULT_CHANNEL}"
MESSAGE="$2"

[ "$CTT_REQUIRE_CONFIRM" = "true" ] && \
  ctt_confirm "Post to $CHANNEL on $CTT_PROFILE?" || return 1

BODY=$(jq -n --arg c "$CHANNEL" --arg t "$MESSAGE" '{channel: $c, text: $t}')
RESP=$(slack_api POST chat.postMessage -d "$BODY")
echo "$RESP" | jq -r 'if .ok then "Posted: \(.ts)" else "ERROR: \(.error)" end'
ctt_audit_log slack "posted to $CHANNEL"
```

Channel can be `#name`, `name`, or `C0XXXXXXX` (channel ID).

### `post-blocks <channel> <blocks-json>` — rich blocks message

For deploy alerts / status posts with formatting. `<blocks-json>` is the
Slack Block Kit JSON array (validate at https://app.slack.com/block-kit-builder/).

```bash
BODY=$(jq -n --arg c "$CHANNEL" --argjson b "$BLOCKS" '{channel: $c, blocks: $b}')
slack_api POST chat.postMessage -d "$BODY"
```

### `thread <channel> <message-ts> <reply>` — reply in thread

```bash
BODY=$(jq -n \
  --arg c "$CHANNEL" \
  --arg ts "$MESSAGE_TS" \
  --arg t "$REPLY" \
  '{channel: $c, thread_ts: $ts, text: $t}')
slack_api POST chat.postMessage -d "$BODY"
```

### `channels [--limit N]` — list channels bot is in

```bash
slack_api GET "conversations.list?types=public_channel,private_channel&limit=${LIMIT:-100}" \
  | jq -r '.channels[] | "\(.id)\t#\(.name)\t\(.num_members) members"'
```

### `history <channel> [--limit N]` — recent messages

```bash
CHID="${1#\#}"
# Validate Slack channel name/ID: a-z, 0-9, hyphen, underscore only
case "$CHID" in
  ''|*[!a-zA-Z0-9_-]*) echo "Invalid channel: $CHID" >&2; return 1 ;;
esac
case "$LIMIT" in
  ''|*[!0-9]*) LIMIT=20 ;;
esac
ENCODED=$(printf %s "$CHID" | jq -sRr @uri)
slack_api GET "conversations.history?channel=$ENCODED&limit=$LIMIT" \
  | jq -r '.messages[] | "\(.ts)\t\(.user // .bot_id)\t\(.text | sub("\n"; " "; "g")[:120])"'
```

### `upload <channel> <file-path> [--comment <text>]` — upload file

Slack now uses 2-step upload (`files.getUploadURLExternal` + `files.completeUploadExternal`):

```bash
SIZE=$(stat -c %s "$FILE" 2>/dev/null || stat -f %z "$FILE")
NAME=$(basename "$FILE")

# Step 1: get upload URL
RESP1=$(slack_api GET "files.getUploadURLExternal?filename=$(printf %s "$NAME" | jq -sRr @uri)&length=$SIZE")
UPLOAD_URL=$(echo "$RESP1" | jq -r '.upload_url')
FILE_ID=$(echo "$RESP1" | jq -r '.file_id')

# Step 2: PUT file content
curl -s -X POST "$UPLOAD_URL" --data-binary "@$FILE" >/dev/null

# Step 3: complete and share
BODY=$(jq -n --arg fid "$FILE_ID" --arg ch "$CHANNEL" --arg c "${COMMENT:-}" '{
  files: [{id: $fid, title: "Uploaded by claude-team-toolkit"}],
  channel_id: $ch,
  initial_comment: $c
}')
slack_api POST files.completeUploadExternal -d "$BODY"
```

### `users` — list workspace users

```bash
slack_api GET users.list | jq -r '.members[] | select(.deleted == false) | "\(.id)\t\(.name)\t\(.profile.real_name)"'
```

## Safety

- Slack messages are **public to channel members** — confirm channel name
  before posting, especially for `#general` or external/shared channels.
- The `require_confirm` profile flag can enforce confirmation for ANY post.
- Bot tokens have **scope** — if 401/`missing_scope`, re-install app with
  the needed scope, don't escalate to user token.
- Channel content read via `history` may contain sensitive info — treat as
  confidential, don't paste publicly.
- Rate limits: Tier 1 (1 req/min), Tier 2 (20/min), Tier 3 (50/min), Tier 4
  (100/min) — `chat.postMessage` is Tier 4. See `Retry-After` header on 429.

## Common Mistakes

- Using `xoxp-` user tokens "to make it work" → security risk. Re-install bot with proper scopes.
- Posting before inviting bot to channel → `not_in_channel` error. `/invite @YourBot` first.
- Block Kit JSON syntax errors → validate at block-kit-builder before posting
- Old upload API (`files.upload`) → deprecated. Use 2-step `getUploadURLExternal` flow.
- Ignoring 429 rate limits → workspace-wide cooldown affects all apps
- Posting to `#general` without confirmation → most workspaces have it on ALL channel

## Token-saving tip

Bot tokens are **per-app-per-workspace**. Create one Slack app per use case
(deploy notifier, on-call alerter, etc.) so revoking one doesn't kill others.
