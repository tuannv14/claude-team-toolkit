# claude-team-toolkit

> Team-ready Claude Code skill pack — for **dev, QA, QC, testers, and team leads**.

A Claude Code plugin bundling integration skills your whole team can install
once and start using immediately. All skills support **multiple accounts**
via INI profile files (AWS-style), so personal/work/client accounts stay
isolated and switchable on demand.

## What's included

| Skill | Slash command | What it does |
|---|---|---|
| **trello** | `/trello` | Manage Trello boards, lists, cards, comments via REST API |
| **azure-devops** | `/azure-devops` | Manage Azure DevOps repos, PRs, work items, pipelines (Services + self-hosted Server) |

More integrations coming as the team needs them. Contributions welcome.

---

## Install

### Option A — via Claude Code plugin (recommended)

```bash
# In Claude Code:
/plugin marketplace add tuannv14/claude-team-toolkit
/plugin install claude-team-toolkit
```

### Option B — clone manually

```bash
git clone https://github.com/tuannv14/claude-team-toolkit.git
# Then point Claude Code at the cloned directory via /plugin marketplace add <path>
```

---

## Quick start

### 1. Install dependencies

Both skills need `curl` (built-in) and `jq`:

```bash
# Windows
choco install jq -y       # or: scoop install jq

# macOS
brew install jq

# Linux
sudo apt install jq       # Debian/Ubuntu
sudo dnf install jq       # Fedora/RHEL
```

### 2. Configure your first account

```bash
# In Claude Code:
/trello configure                # interactive — prompts for key + token
/azure-devops configure          # interactive — prompts for org URL + PAT
```

This creates:
- `~/.trello/credentials` (mode 600)
- `~/.azure-devops/credentials` (mode 600)

### 3. Use it

```bash
/trello card https://trello.com/c/AbCd1234
/trello boards
/trello create <listId> "New task" "Description here"

/azure-devops projects
/azure-devops pr-list MyRepo MyProject
/azure-devops pr-create MyRepo feat/x main "PR title" "Body"
```

---

## Multi-account workflow

Add as many accounts as you need:

```bash
/trello configure                          # creates [default]
/trello configure                          # add another → name it "work"
/trello configure                          # add another → name it "personal"

/trello profile list                       # see all profiles
/trello profile use work                   # switch default
/trello profile current                    # show active

/trello --profile personal boards          # one-off override
TRELLO_PROFILE=work /trello cards <listId> # via env
```

Same commands exist for `/azure-devops`. Profile resolution priority:

1. `--profile <name>` flag
2. `TRELLO_PROFILE` / `AZDO_PROFILE` env var
3. Active profile (`profile use`)
4. `[default]` section

---

## Security model

This is the most important part — **read it before adding credentials**.

| Concern | How the skills handle it |
|---|---|
| Credential files | Stored at `~/.trello/credentials` and `~/.azure-devops/credentials`, mode `0600`. The skill **refuses to load** if the file is world-readable. |
| Accidental commits | Shipped `.gitignore` blocks `**/credentials`, `**/*.pat`, `**/*.token`, `.env`, and common secret patterns. |
| Display masking | Tokens/PATs are shown as `****<last4>` only — never in full. |
| Validation before save | Configure flow calls a real API endpoint (e.g., `members/me`, `connectionData`); refuses to save invalid credentials. |
| Prompt injection | Card descriptions, comments, work item bodies are treated as **untrusted input**. The skills will not act on instructions found inside that content — only on commands you type in the terminal. |
| Mutation safety | Destructive ops (create/move/comment/archive/PR-create) require explicit user request — never triggered by content scraped from the API. |
| Per-service scope | Each skill stores credentials in its own directory. Revoking one service does not affect another. |
| Self-signed certs | Azure DevOps Server with self-signed cert: opt-in `insecure = true` per profile. Never enabled by default. |
| Least privilege | Azure DevOps skill documents required PAT scopes per operation — avoid `Full access`. |

### What the skills will **never** do

- Write your credentials to chat output, commit messages, transcripts, or any
  file other than the designated credentials file.
- Echo the full key/token/PAT — only the last 4 characters.
- Mutate data (create/update/delete) based on instructions discovered inside
  card content, comments, or work item descriptions.
- Bypass TLS verification unless you explicitly opt in via `insecure = true`.

### If a credential is compromised

- **Trello:** revoke at https://trello.com/<username>/account → "Power-Ups
  and Integrations" → Revoke.
- **Azure DevOps:** revoke at `https://<your-org-or-server>/_usersSettings/tokens`.

---

## For team leads / admins

- The toolkit is **stateless** at the team level — each user has their own
  credentials. Nothing is shared.
- Recommend the team use **least-privilege PATs** (the Azure DevOps skill
  documents the minimal scopes per operation).
- For internal Azure DevOps Server with self-signed certs, decide once whether
  to enable `insecure = true` and document it for the team.

---

## Roadmap

Planned skills (PRs welcome):

- [ ] Slack — channels, DMs, thread management
- [ ] Jira — issues, sprints, comments
- [ ] GitLab — MRs, issues, pipelines
- [ ] Notion — pages, databases
- [ ] Linear — issues, cycles

---

## License

MIT — see [LICENSE](LICENSE).
