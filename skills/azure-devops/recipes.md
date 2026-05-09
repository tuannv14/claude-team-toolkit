# /azure-devops — recipes (load on demand)

> Loaded by SKILL.md only when user invokes a specific dispatch verb.

## Helpers (already loaded in SKILL.md)

```bash
source "$HOME/.claude-team-toolkit/lib/credentials.sh"
ctt_load_creds azure-devops "$PROFILE"

# Build Basic auth (username empty, PAT in password slot)
AZDO_AUTH=$(printf ":%s" "$CTT_PAT" | base64 -w0 2>/dev/null || printf ":%s" "$CTT_PAT" | base64)
[ "$CTT_INSECURE" = "true" ] && AZDO_CURL="curl -sk --ssl-no-revoke" || AZDO_CURL="curl -s --ssl-no-revoke"
ORG="${CTT_ORG_URL%/}"
APIV="${CTT_API_VERSION:-7.0}"
PROJECT_DEFAULT="$CTT_PROJECT"

azdo_api() {
  local method="$1" path="$2"; shift 2
  local sep="?"; [[ "$path" == *\?* ]] && sep="&"
  $AZDO_CURL -X "$method" \
    -H "Authorization: Basic $AZDO_AUTH" \
    -H "Content-Type: application/json" \
    -H "Accept: application/json" \
    "$@" \
    "${ORG}${path}${sep}api-version=${APIV}"
}
```

## Dispatch — read

### `projects` — list projects
```bash
azdo_api GET "/_apis/projects" | jq -r '.value[] | "\(.id)\t\(.name)\t\(.state)"'
```

### `repos [project]` — list repos
```bash
PROJECT="${1:-$PROJECT_DEFAULT}"
azdo_api GET "/$PROJECT/_apis/git/repositories" \
  | jq -r '.value[] | "\(.id)\t\(.name)\t\(.webUrl)"'
```

### `branches <repo> [project]` — list branches
```bash
azdo_api GET "/$PROJECT/_apis/git/repositories/$REPO/refs?filter=heads" \
  | jq -r '.value[] | .name | sub("^refs/heads/"; "")'
```

### `pr-list <repo> [project] [--status active|completed|abandoned|all]`
```bash
azdo_api GET "/$PROJECT/_apis/git/repositories/$REPO/pullrequests?searchCriteria.status=${STATUS:-active}" \
  | jq -r '.value[] | "\(.pullRequestId)\t\(.status)\t\(.title)\t\(.createdBy.displayName)"'
```

### `pr-get <pr-id> <repo> [project]`
```bash
azdo_api GET "/$PROJECT/_apis/git/repositories/$REPO/pullrequests/$PR_ID"
```

### `wi-get <id>` — fetch work item with all fields
```bash
azdo_api GET "/_apis/wit/workitems/$WI_ID?\$expand=all"
```

### `wi-query <wiql>` — run a WIQL query
```bash
BODY=$(jq -n --arg q "$WIQL" '{query: $q}')
azdo_api POST "/$PROJECT/_apis/wit/wiql" -d "$BODY" | jq -r '.workItems[].id'
```

WIQL example:
```sql
SELECT [System.Id], [System.Title], [System.State]
FROM workitems
WHERE [System.AssignedTo] = @Me AND [System.State] <> 'Closed'
ORDER BY [System.ChangedDate] DESC
```

### `pipelines [project]`
```bash
azdo_api GET "/$PROJECT/_apis/pipelines" | jq -r '.value[] | "\(.id)\t\(.name)"'
```

### `builds [project] [--top N]`
```bash
azdo_api GET "/$PROJECT/_apis/build/builds?\$top=${TOP:-20}" \
  | jq -r '.value[] | "\(.id)\t\(.buildNumber)\t\(.status)\t\(.result // "—")"'
```

## Dispatch — write (require ctt_audit_log)

### `pr-create <repo> <source-branch> <target-branch> <title> [description]`
```bash
BODY=$(jq -n \
  --arg s "refs/heads/$SOURCE" \
  --arg t "refs/heads/$TARGET" \
  --arg title "$TITLE" \
  --arg desc "$DESC" \
  '{sourceRefName: $s, targetRefName: $t, title: $title, description: $desc}')
azdo_api POST "/$PROJECT/_apis/git/repositories/$REPO/pullrequests" -d "$BODY"
```

### `pr-comment <pr-id> <repo> <text>` — add comment thread
```bash
BODY=$(jq -n --arg t "$TEXT" '{
  comments: [{parentCommentId: 0, content: $t, commentType: 1}],
  status: 1
}')
azdo_api POST "/$PROJECT/_apis/git/repositories/$REPO/pullrequests/$PR_ID/threads" -d "$BODY"
```

### `wi-create <type> <title> [project]` — create work item
```bash
BODY=$(jq -n --arg t "$TITLE" '[{op:"add", path:"/fields/System.Title", value:$t}]')
azdo_api POST "/$PROJECT/_apis/wit/workitems/\$$TYPE" \
  -H "Content-Type: application/json-patch+json" \
  -d "$BODY"
```

### `pipeline-run <pipeline-id> [project] [--branch <name>]`
```bash
BODY=$(jq -n --arg b "${BRANCH:-main}" '{
  resources: {repositories: {self: {refName: ("refs/heads/" + $b)}}}
}')
azdo_api POST "/$PROJECT/_apis/pipelines/$PIPELINE_ID/runs" -d "$BODY"
```

## `configure` interactive

Prompt: profile name → org URL → PAT (hidden) → default project → API version
(default 7.0; suggest 5.1 if URL doesn't contain `dev.azure.com`) → insecure
(y/N for self-signed). Validate via `_apis/connectionData`. Save to creds
file (mode 600).
