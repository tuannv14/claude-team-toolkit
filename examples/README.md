# Examples

Sanitized templates for setting up `claude-team-toolkit` skills.

| File | Purpose |
|---|---|
| `.testcase-schema.example.yml` | Column mapping for `/xlsx-testcases` — copy to your xlsx folder |
| `.env.example` | Per-call profile switch via env vars |
| `trello-credentials.example` | Multi-account Trello creds template |
| `azure-devops-credentials.example` | ADO Services + Server multi-org template |

## How to use

1. Copy the relevant file to its target location (e.g. `~/.trello/credentials`).
2. Fill in your real credentials.
3. `chmod 600 <file>` (the skills will refuse to load world-readable files
   on POSIX).
4. Test with the skill's `configure` or `profile current` subcommand.

## NEVER commit credential files

The shipped `.gitignore` blocks `**/credentials`, `**/*.pat`, `**/*.token`,
keys, certs, `.env`, GCP service-account JSONs, kubeconfig, etc. If you
add new credential file patterns, update `.gitignore` first.

If you accidentally committed a credential, treat it as compromised:
**revoke immediately** (see [README.md](../README.md#if-a-credential-is-compromised)),
then `git filter-repo` or BFG to remove from history.
