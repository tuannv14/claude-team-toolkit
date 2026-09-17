# MCP servers for azure-devops, heroku and linear

These three skills talk to their service **only** through an MCP server. They
issue no REST calls of their own, and there is no curl fallback: a hand-written
request to `api.linear.app`, `api.heroku.com` or any `/_apis/` URL is exactly
what the guard hook below is there to refuse.

That is a deliberate trade. What it buys:

1. **The server keeps the credential.** The token is read by the server process.
   No skill puts it on a command line, in a temp file, or in the process list.
2. **Permission tiers are enforced by the host, before the tool runs.** A denied
   tool cannot be called. A `ctt_confirm` prompt can be answered "yes" by a model
   in a hurry; a deny rule cannot.
3. **One boundary instead of two.** With a curl fallback in the skill, every
   safety rule has to be written twice and the weaker copy is the one that gets
   used.

What it costs: the `--profile` switch and everything built on it. An MCP server
is configured once, with one credential. The `read_only` and `require_confirm`
flags, and `ctt_audit_log`, apply to the toolkit's curl skills and have no
effect here — the tier list and the guard hooks replace them. To work across
several accounts of one service, declare one server per account under distinct
names.

The toolkit ships no MCP servers. A server is a process with its own credentials
and update cycle, and these three systems differ at every company: Azure DevOps
Server on-premises is not Azure DevOps Services, and a scoped Heroku token is not
a personal one. The toolkit ships the skills that drive them; this document is
the wiring.

## Coming from 0.12.x or earlier

Up to 0.12.2 these three skills were curl-based, with `~/.linear/credentials`,
`~/.azure-devops/credentials` and `~/.heroku/credentials` profiles driving them.
Two things to do once:

1. **Delete any hand-copied folders** for these three under `~/.claude/skills/`.
   A loose copy takes precedence over the plugin's, so an old curl-based copy
   would tell Claude to make exactly the REST calls the guard hook now refuses.
   Copies of the other thirteen skills are stale but harmless.
2. **`~/.linear/credentials` is now unused** — Linear authenticates by OAuth
   inside the MCP server. Delete it, and revoke the personal API key it holds if
   nothing else uses it. `~/.heroku/credentials` and `~/.azure-devops/credentials`
   stay, but they are read by the MCP servers now, not by the skills.

Nothing else changes. `--profile`, `read_only` and the audit log still work for
the other thirteen skills exactly as before.

## `.mcp.json`

At the root of the project that needs them:

```json
{
  "mcpServers": {
    "azure-devops": {
      "command": "node",
      "args": ["${CLAUDE_PROJECT_DIR:-.}/.claude/mcp/azure-devops/launch.mjs"]
    },
    "heroku": {
      "command": "node",
      "args": ["${CLAUDE_PROJECT_DIR:-.}/.claude/mcp/heroku/launch.mjs"]
    },
    "linear": {
      "type": "http",
      "url": "https://mcp.linear.app/mcp"
    }
  }
}
```

Two are local processes the editor starts; Linear is hosted. Run `/mcp` once to
authenticate Linear; the other two need no interactive step.

Prefer a **launcher script** over putting the command straight in `.mcp.json`.
An MCP server is started by the editor, not by a shell: it inherits no profile,
no `PATH` edits, and no working directory you can rely on. A launcher resolves
its own paths, picks the credential deliberately, and turns the predictable
setup failures into a sentence instead of a stack trace.

## Per-server notes

### linear

Hosted at `https://mcp.linear.app/mcp`, OAuth through `/mcp`. Nothing to
install. This is the one server that is the same everywhere.

### heroku

The MCP server ships **inside the Heroku CLI** (`heroku mcp:start`, CLI v10.8.1
or later). Do not install the npm package `@heroku/mcp-server`: as published its
ESM imports `@modelcontextprotocol/sdk/server/mcp` with no file extension, which
no 1.x SDK resolves, so it exits immediately with `ERR_MODULE_NOT_FOUND`.

Run bare, `heroku mcp:start` authenticates with whatever `~/.netrc` holds, which
on a developer machine is a full-access interactive login. Point it at a scoped
token instead:

```bash
heroku authorizations:create -d "claude mcp read-only" -s identity,read
```

Store it as an `[mcp]` profile in `~/.heroku/credentials` and have the launcher
export it as `HEROKU_API_KEY`.

**The `identity` scope is not optional.** A token scoped `read` alone makes the
CLI resolve the account before almost every command, `GET /account` returns 404,
and `list_apps` fails with "Couldn't find that user".

An empty `HEROKU_API_KEY` is not the same as an absent one: the CLI reads the
empty string as an explicit credential and will not fall back to `~/.netrc`.
Unset the variable rather than setting it empty.

A scoped token and the deny rules are two independent layers. The deny rules stop
a write from being attempted; the token makes the API refuse it even if a rule is
ever removed.

### azure-devops

Microsoft's `@azure-devops/mcp` targets Azure DevOps **Services**. It does not
support on-premises Azure DevOps **Server**, which is why a team on-prem ends up
vendoring a server rather than installing one. Two adaptations are typical:

- **API version.** An on-prem server's newest REST API may be 5.1 while the
  tools were written against the cloud's 7.1, which every endpoint rejects with
  `VssVersionOutOfRangeException`. Rewrite the parameter in one place in the
  request helper, so a tool added later inherits the fix.
- **Credentials.** The server inherits no shell profile, so read the PAT from a
  file. Reading `~/.azure_devops_pat` before `~/.azure-devops/credentials` is
  worth doing: the two drift, and an expired INI copy sitting alongside a working
  raw file is a confusing failure. Make the 401 name which file supplied the
  token.

## Permission tiers

Sort every tool of every server into allow, ask or deny in your project's
`.claude/settings.json`. Reads allow, writes ask, state-changing operations deny.
With no curl fallback, this tier list **is** the safety boundary.

A ready-made starting point ships with the toolkit:
[`examples/mcp-permissions.example.json`](../examples/mcp-permissions.example.json)
— 53 read tools allowed, 23 state-changing ones denied. Merge its `permissions`
block into your settings.

Two deny entries are easy to miss:

- **`mcp__heroku__pg_credentials`** changes nothing, so it reads like a read
  tool. It prints live database credentials. Deny it.
- **`mcp__heroku__pg_psql`** is an interactive shell against the database. Deny
  it; use the `postgres` skill with a `read_only = true` profile.

An unlisted tool is not denied — it prompts. Denying is a decision; leaving a
tool out is not. The example file leaves Linear's `save_*` write tools unlisted
on purpose, so they prompt until the team decides.

Tool names are per-server. An on-premises Azure DevOps server's names will not
match the cloud one's. Check yours with `/mcp` before copying the file wholesale.

## Two guard hooks

A tier list has holes that no permission rule closes, so **the toolkit ships two
`PreToolUse` hooks on `Bash`** and wires them in `hooks/hooks.json`. They are
active wherever the plugin is enabled — you do not configure them.

- **`hooks/heroku_guard.py`** refuses state-changing Heroku CLI subcommands.
  `heroku ps:scale` typed into Bash is not an MCP tool call, so no `mcp__*` rule
  matches it. A `Bash(heroku pg:psql:*)` deny rule does not help either: it
  matches by prefix, so `cd /tmp && heroku pg:psql`, `bash -c "..."`, a leading
  `VAR=value`, or a full path to the binary all slip past. The hook receives the
  whole command and scans every token after each `heroku`.
- **`hooks/mcp_only_guard.py`** refuses an HTTP client from the shell against
  `api.linear.app`, `api.heroku.com`, or any URL containing `/_apis/`. Without
  it the tier list is decoration: one `curl` gets around it.

`git` is untouched by both. Push, fetch and clone talk to the same Azure DevOps
host and never carry an `_apis` path.

Both **fail open**: any internal error allows the command and prints a loud
warning to stderr. A guard that breaks every Bash call gets switched off within a
day, and a switched-off guard protects nothing. Neither is a sandbox.

Both over-block in one known way, deliberately. `echo heroku ps:scale` is
refused, because the guard cannot tell a mention from `$(echo heroku ps:scale)`.
A false positive costs one manually-run command; a false negative costs a
production mutation. Heredoc bodies and `-m` commit messages *are* treated as
data, so writing about these commands in a commit message works.

To turn both off: **`CTT_GUARDS=off`** in the environment. A plugin-wide hook
needs a documented way out; editing a file inside the plugin cache is not one.

## Checking what is actually connected

```bash
claude mcp list
```

Inside a session, `/mcp` shows connection state and handles OAuth. A server that
says `needs_auth` can only be signed in by you, interactively.

A tool that is configured but never appears is usually one of three things: the
server failed to start (read its stderr), the tool is denied by a rule, or the
server is project-scoped and you opened a different project.

## If the MCP server is not configured

The skill says so and stops. It does not fall back to REST. Wire the server, or
use the service's own CLI or web UI for that task.
