# /slack — recipes (load on demand)

> Loaded by SKILL.md only when user invokes a specific dispatch verb.

## Helpers (already loaded in SKILL.md)

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

## Dispatch — read

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

### `users` — list workspace users

```bash
slack_api GET users.list | jq -r '.members[] | select(.deleted == false) | "\(.id)\t\(.name)\t\(.profile.real_name)"'
```

## Dispatch — write (require ctt_audit_log; conditional ctt_confirm)

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

### `post-blocks <channel> <blocks-json>` — rich Block Kit message

For deploy alerts / status posts. `<blocks-json>` is the Slack Block Kit JSON
array (validate at https://app.slack.com/block-kit-builder/).

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
