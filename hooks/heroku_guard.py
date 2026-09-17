# Heroku destructive-command guard — Claude Code PreToolUse hook.
#
# Shipped by claude-team-toolkit and wired in hooks/hooks.json. It applies
# wherever the plugin is enabled.
#
# WHY A HOOK AND NOT A PERMISSION RULE
# A `Bash(heroku pg:psql:*)` deny rule matches the raw command string by prefix,
# so every shell wrapping defeats it:
#     cd /tmp && heroku pg:psql          -> string starts with "cd", rule misses
#     echo "..." | heroku pg:psql        -> starts with "echo", rule misses
#     bash -c "heroku pg:psql"           -> starts with "bash", rule misses
#     HEROKU_APP=x heroku pg:psql        -> starts with an assignment, rule misses
#     /c/Program\ Files/heroku/bin/heroku pg:psql  -> starts with a path, rule misses
# This hook receives the WHOLE command and scans it, so wrapping does not help.
#
# WHAT IT BLOCKS
# Claude running a state-changing Heroku command. Reads stay open: pg:info, pg:ps,
# pg:diagnose, logs, releases, ps, apps, config (bare), addons, pipelines,
# auth:whoami. The human is never blocked — they run the command in their own
# terminal.
#
# TO TURN IT OFF
# Set CTT_GUARDS=off in the environment. It is a plugin-wide hook, so a project
# that wants the heroku CLI open needs a documented way out; silently editing a
# file inside the plugin cache is not one.
#
# FAIL-OPEN, DELIBERATELY
# Any internal error allows the command and prints a loud warning to stderr. A
# guard that breaks every Bash call gets switched off within a day, and a
# switched-off guard protects nothing. The trade-off is stated so nobody mistakes
# this for a sandbox.
import sys, json, re, os

# Subcommands that change state, cost money, or execute arbitrary code/SQL.
DANGEROUS = [
    # Postgres — pg:psql is arbitrary SQL against the app database
    "pg:psql", "pg:reset", "pg:promote", "pg:upgrade", "pg:kill", "pg:killall",
    "pg:unfollow", "pg:backups:restore", "pg:backups:delete", "pg:backups:schedule",
    "pg:backups:unschedule", "pg:credentials:rotate", "pg:credentials:destroy",
    "pg:credentials:create", "pg:links:create", "pg:links:destroy", "pg:maintenance:run",
    "redis:reset", "redis:promote", "redis:cli",
    # Dynos and arbitrary execution inside them
    "ps:restart", "ps:scale", "ps:stop", "ps:kill", "ps:type",
    "run", "run:detached", "run:inside", "restart",
    # App lifecycle
    "apps:destroy", "apps:rename", "apps:transfer", "apps:create", "destroy", "create",
    # Config vars — these hold every runtime secret
    "config:set", "config:unset", "config:edit",
    # Add-ons — can provision paid resources
    "addons:create", "addons:destroy", "addons:attach", "addons:detach",
    "addons:upgrade", "addons:downgrade", "addons:rename",
    # Release and deploy paths
    "pipelines:promote", "pipelines:destroy", "pipelines:create", "pipelines:add",
    "pipelines:remove", "releases:rollback", "rollback", "releases:retry",
    # Availability
    "maintenance:on", "maintenance:off",
    # Account, access and credentials
    "access:add", "access:remove", "access:update", "authorizations:create",
    "authorizations:revoke", "authorizations:rotate", "keys:add", "keys:remove",
    "keys:clear", "members:add", "members:remove", "members:set",
    # Build and runtime configuration
    "buildpacks:add", "buildpacks:set", "buildpacks:remove", "buildpacks:clear",
    "labs:enable", "labs:disable", "features:enable", "features:disable",
    "stack:set", "domains:add", "domains:remove", "domains:clear",
    "certs:add", "certs:remove", "certs:update",
    "drains:add", "drains:remove", "webhooks:add", "webhooks:remove",
    "spaces:create", "spaces:destroy", "spaces:rename",
]
# Prefix families: any subcommand starting with these is treated as dangerous.
DANGEROUS_PREFIXES = ("pg:settings:", "ps:autoscale:", "dyno:", "certs:auto:")

# A heroku invocation: optional directory prefix, the binary, optional .cmd/.exe.
HEROKU_CALL = re.compile(
    r"(?:^|[\s;&|(){}`'\"])(?:[\w.~/\\:+-]*[/\\])?heroku(?:\.cmd|\.exe)?(?=\s|$)", re.I)
# Shell separators that end one command and begin the next.
SEPARATOR = re.compile(r"(?:\|\||&&|[;\n|&])")
# git push to a heroku remote is an out-of-band production deploy.
GIT_PUSH_HEROKU = re.compile(r"git\s+push\b[^;\n|&]*\bheroku[\w-]*\b", re.I)

HEREDOC = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][\w]*)\1.*?^\s*\2\s*$", re.S | re.M)
GIT_MESSAGE_ARG = re.compile(r"(?<=\s)(?:-m|--message(?:=|\s+))\s*('([^']*)'|\"([^\"]*)\")")


def strip_data_regions(command):
    """Remove text that is DATA, never code, so merely naming a command is allowed.

    Two regions qualify, and the distinction is what keeps this safe:
      - a heredoc body (`git commit -F - <<'MSG' ... MSG`) is fed to a program's
        stdin; nothing in it is executed by the shell
      - the quoted argument of `-m` / `--message` is a commit message
    A quoted argument in general is NOT stripped, because `bash -c "heroku
    pg:psql"` is a quoted string that really does execute.
    """
    cleaned = HEREDOC.sub(" ", command)
    cleaned = GIT_MESSAGE_ARG.sub(" ", cleaned)
    return cleaned


def offending(command):
    """Return a reason string if the command changes Heroku state, else None."""
    if not command:
        return None
    command = strip_data_regions(command)

    if GIT_PUSH_HEROKU.search(command):
        return ("`git push` to a Heroku remote is a deploy, run from a workstation "
                "and outside whatever pipeline this project deploys through.")

    for m in HEROKU_CALL.finditer(command):
        # Everything after this heroku token, up to the next shell separator.
        tail = command[m.end():]
        cut = SEPARATOR.search(tail)
        if cut:
            tail = tail[:cut.start()]
        # Drop flags and VAR=value assignments, then check EVERY surviving token.
        # Scanning all of them rather than just the first is deliberate: a
        # value-taking flag shifts the subcommand along, so `heroku --app foo
        # ps:scale web=2` puts the real subcommand in third place. A false
        # positive costs one manually-run read command; a false negative costs a
        # production mutation, so the trade is not close.
        for w in tail.split():
            if w.startswith("-") or "=" in w.split("/")[0]:
                continue
            bare = w.strip("\"'`")
            if bare in DANGEROUS or bare.startswith(DANGEROUS_PREFIXES):
                return "`heroku %s` changes Heroku state." % bare
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
        reason = offending(command)
        if not reason:
            sys.exit(0)

        message = (
            "BLOCKED by claude-team-toolkit heroku_guard.py — %s\n\n"
            "A Heroku API token is account-wide: no token writes to staging but not "
            "to production. So a state-changing command from a model is treated as "
            "something that needs a person, every time.\n\n"
            "What to do instead:\n"
            "  - Read-only diagnostics: use the `heroku` MCP tools (`ps_list`, "
            "`pg_info`, `pg_ps`, `pg_outliers`, `get_app_logs`), or a heroku read "
            "command in your own terminal.\n"
            "  - If the change is genuinely needed: run it yourself, or ask Claude "
            "to hand you the exact command.\n"
            "  - To lift this guard everywhere: set CTT_GUARDS=off.\n\n"
            "Command: %s"
        ) % (reason, command.strip()[:400])

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
            "heroku_guard.py failed (%s: %s) and ALLOWED the command. "
            "The guard is not protecting you right now — fix it.\n"
            % (type(exc).__name__, exc))
        sys.exit(0)


if __name__ == "__main__":
    main()
