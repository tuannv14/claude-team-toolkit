---
name: slack
description: "Use when user references Slack, *.slack.com/archives/ URLs, channel mentions like #deploys, or asks to post/thread/upload-file/fetch-history/send deploy or incident alert. Multi-workspace via SLACK_PROFILE."
user-invocable: true
allowed-tools:
  - Read
  - Bash
---

# /slack — Slack Web API (multi-workspace)

REST against `https://slack.com/api/`. Bearer auth with bot OAuth token.
Profiles isolate workspaces. Profile resolution: `--profile` →
`SLACK_PROFILE` → `~/.slack/active_profile` → `[default]`.

## Overview

REST against Slack Web API with bot OAuth tokens (`xoxb-`). Profiles isolate
workspaces. Default to bot tokens — never use user tokens (`xoxp-`) which
carry the user's full permissions.

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
require_confirm = true                   # gate every post
```

**Get a bot token:**

1. https://api.slack.com/apps → Create New App → From scratch
2. OAuth & Permissions → add bot scopes (least privilege):
   `chat:write`, `channels:read`, `users:read`, `files:write`
3. Install to Workspace → copy "Bot User OAuth Token" (starts with `xoxb-`)
4. Invite the bot to channels: `/invite @YourBot`

**Never use `xoxp-` user tokens** unless absolutely necessary.

## Helpers

> Shared profile/INI/`ctt_*` pattern reference: [profiles-and-credentials](../profiles-and-credentials/SKILL.md).

```bash
source "$HOME/.claude-team-toolkit/lib/credentials.sh"
source "$HOME/.claude-team-toolkit/lib/confirm.sh"
ctt_load_creds slack "$PROFILE"
```

`slack_api()` wrapper and full dispatch implementations live in
**[recipes.md](recipes.md)** — load when user invokes a specific verb.

| Verb | Mutating? | Confirm |
|---|---|---|
| `channels`, `history`, `users` | no | — |
| `post`, `post-blocks`, `thread` | yes | `ctt_audit_log`; `ctt_confirm` if profile `require_confirm` |
| `upload` | yes | `ctt_audit_log` |

## Reference files (load on demand)

- **`recipes.md`** — full curl + jq implementations for every verb above. Load when user invokes a specific dispatch verb.

## Common Mistakes

- Using `xoxp-` user tokens "to make it work" → security risk. Re-install bot with proper scopes.
- Posting before inviting bot to channel → `not_in_channel` error. `/invite @YourBot` first.
- Block Kit JSON syntax errors → validate at block-kit-builder before posting
- Old upload API (`files.upload`) → deprecated. Use 2-step `getUploadURLExternal` flow.
- Ignoring 429 rate limits → workspace-wide cooldown affects all apps
- Posting to `#general` without confirmation → most workspaces have it on ALL channel

## Safety

- Slack messages are **public to channel members** — confirm channel name before posting, especially for `#general` or external/shared channels.
- The `require_confirm` profile flag enforces confirmation for ANY post.
- Bot tokens have **scope** — if 401/`missing_scope`, re-install app with the needed scope, don't escalate to user token.
- Channel content read via `history` may contain sensitive info — treat as confidential.
- Rate limits: Tier 4 (`chat.postMessage` = 100/min). Honor `Retry-After` on 429.

## Token-saving tip

Bot tokens are **per-app-per-workspace**. Create one Slack app per use case
(deploy notifier, on-call alerter, etc.) so revoking one doesn't kill others.
