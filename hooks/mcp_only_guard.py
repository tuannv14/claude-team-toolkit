# MCP-only guard for Azure DevOps, Heroku and Linear — Claude Code PreToolUse hook.
#
# Shipped by claude-team-toolkit and wired in hooks/hooks.json. It applies
# wherever the plugin is enabled.
#
# WHY
# The azure-devops, heroku and linear skills reach their service only through an
# MCP server, and the permission tiers that decide what may be read and what may
# never be written are written against MCP tool names (mcp__heroku__pg_psql and
# friends). A raw `curl` to the same API answers to none of those rules: it is one
# Bash call, indistinguishable from any other, and it can do everything the token
# allows. Closing that path is what makes the tiers mean something — and what
# makes "MCP-only" true in practice rather than by convention.
#
# WHAT IT BLOCKS
# An HTTP client invoked from the shell against:
#   - api.linear.app          Linear's GraphQL API (Linear has no REST API)
#   - api.heroku.com          the Heroku Platform API
#   - any URL containing /_apis/   Azure DevOps REST, on any host
# The Azure DevOps rule is written as a path shape rather than a hostname on
# purpose: `_apis` is universal to Azure DevOps while the hostname is specific to
# one deployment, and a plugin cannot know the deployment.
#
# WHAT IT DOES NOT BLOCK
# git. Push, fetch and clone talk to the same Azure DevOps host and are the
# supported way to move code; they never carry an `_apis` path. Nor the heroku
# CLI — heroku_guard.py already refuses the state-changing half of it. Nor any
# other service: the toolkit's other skills are curl-based by design.
#
# TO TURN IT OFF
# Set CTT_GUARDS=off in the environment.
#
# FAIL-OPEN, DELIBERATELY
# Any internal error allows the command and prints a loud warning to stderr, for
# the same reason as heroku_guard.py: a guard that breaks every Bash call gets
# switched off, and a switched-off guard protects nothing.
import sys, json, re, os

# Programs that fetch a URL given on the command line.
HTTP_CLIENTS = (
    "curl", "curl.exe", "wget", "wget.exe", "httpie", "http", "https",
    "invoke-webrequest", "invoke-restmethod", "iwr", "irm",
)

BLOCKED = (
    ("api.linear.app", "Linear's GraphQL API", "linear"),
    ("api.heroku.com", "the Heroku Platform API", "heroku"),
    ("/_apis/", "the Azure DevOps REST API", "azure-devops"),
)

SEPARATOR = re.compile(r"(?:\|\||&&|[;\n|&])")

# Same two data regions heroku_guard.py strips, and duplicated on purpose: a
# hook is a standalone script, and a shared import would make each guard depend
# on the other being present and unbroken. Keep the two copies in step.
HEREDOC = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][\w]*)\1.*?^\s*\2\s*$", re.S | re.M)
GIT_MESSAGE_ARG = re.compile(r"(?<=\s)(?:-m|--message(?:=|\s+))\s*('([^']*)'|\"([^\"]*)\")")


def strip_data_regions(command):
    """Remove text that is DATA, never code, so merely naming a URL is allowed."""
    cleaned = HEREDOC.sub(" ", command)
    cleaned = GIT_MESSAGE_ARG.sub(" ", cleaned)
    return cleaned


def is_http_client(token):
    bare = token.strip("\"'`").rsplit("/", 1)[-1].rsplit("\\", 1)[-1].lower()
    return bare in HTTP_CLIENTS


def offending(command):
    """Return (reason, server) if the command calls one of these APIs directly."""
    if not command:
        return None
    command = strip_data_regions(command)

    # Split into single commands so a URL in one segment cannot be blamed on a
    # client in another: `echo https://api.linear.app/graphql && ls` is not a call.
    for segment in SEPARATOR.split(command):
        if not any(is_http_client(w) for w in segment.split()):
            continue
        lowered = segment.lower()
        for needle, description, server in BLOCKED:
            if needle in lowered:
                return (
                    "this calls %s directly from the shell" % description,
                    server,
                )
    return None


def main():
    if os.environ.get("CTT_GUARDS", "").lower() in ("off", "0", "false"):
        sys.exit(0)

    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)  # unreadable payload -> allow, see FAIL-OPEN note

    try:
        if payload.get("tool_name") != "Bash":
            sys.exit(0)
        command = (payload.get("tool_input") or {}).get("command") or ""
        found = offending(command)
        if not found:
            sys.exit(0)
        reason, server = found

        message = (
            "BLOCKED by claude-team-toolkit mcp_only_guard.py — %s.\n\n"
            "The azure-devops, heroku and linear skills reach their service through "
            "an MCP server, never through a hand-written HTTP call. The reason is not "
            "style: what may be read and what may never be written is decided by "
            "permission rules on MCP tool names, and a raw HTTP call is subject to "
            "none of them.\n\n"
            "What to do instead:\n"
            "  - Use an `mcp__%s__*` tool. If none covers what you need, say so "
            "rather than routing around this.\n"
            "  - git is unaffected: clone, fetch and push are the supported way to "
            "move code.\n"
            "  - No MCP server configured? See docs/mcp-servers.md in the plugin.\n"
            "  - To lift this guard everywhere: set CTT_GUARDS=off.\n\n"
            "Command: %s"
        ) % (reason, server, command.strip()[:400])

        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": message,
            }
        }))
        sys.stderr.write(message + "\n")
        sys.exit(2)  # exit 2 blocks even if the JSON shape is not recognised
    except SystemExit:
        raise
    except Exception as exc:  # deliberate fail-open
        sys.stderr.write(
            "mcp_only_guard.py failed (%s: %s) and ALLOWED the command. "
            "The guard is not protecting you right now — fix it.\n"
            % (type(exc).__name__, exc))
        sys.exit(0)


if __name__ == "__main__":
    main()
