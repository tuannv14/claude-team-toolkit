# /linear — recipes (load on demand)

> Loaded by SKILL.md only when the user invokes a specific dispatch verb.
> Endpoint: `https://api.linear.app/graphql` (POST only, one URL for everything).

## Helpers

```bash
source "$HOME/.claude-team-toolkit/lib/credentials.sh"
source "$HOME/.claude-team-toolkit/lib/confirm.sh"
ctt_load_creds linear "$PROFILE"

API="https://api.linear.app/graphql"
TMP="${TMPDIR:-/tmp}"

# NOTE: no "Bearer" — that prefix is for OAuth tokens only.
# $1 = path to a JSON file holding {"query": ..., "variables": {...}}
linear_gql() {
  curl -s --ssl-no-revoke -X POST \
    -H "Authorization: $CTT_API_KEY" \
    -H "Content-Type: application/json" \
    --data-binary @"$1" "$API"
}

# Fail loudly on GraphQL errors. Linear answers 200 with an errors array for
# most failures, and 400 + RATELIMITED when throttled — status alone proves
# nothing. $1 = response file. Returns 1 and prints the messages on error.
linear_check() {
  if jq -e '.errors and (.errors | length > 0)' "$1" >/dev/null 2>&1; then
    jq -r '.errors[] | "linear: \(.extensions.code // "ERROR"): \(.message)"' "$1" >&2
    if jq -e '[.errors[].extensions.code] | index("RATELIMITED")' "$1" >/dev/null 2>&1; then
      echo "linear: rate limited (2500 req/h per user). Wait for the reset, do not retry in a loop." >&2
    fi
    return 1
  fi
}

# Write the query document to a file so it reaches jq via --rawfile.
lq() { printf '%s' "$1" > "$TMP/q.graphql"; }

# Extract ENG-123 from a bare key or a linear.app URL.
lin_id() {
  case "$1" in
    *linear.app/*) echo "$1" | sed -E 's|.*/issue/([A-Za-z0-9]+-[0-9]+).*|\1|' ;;
    *)             echo "$1" ;;
  esac
}

# Resolve a team key (ENG) to its UUID — issueCreate needs the UUID.
lin_team_uuid() {
  lq 'query($k:String!){ teams(filter:{key:{eq:$k}}, first:1){ nodes{ id key name } } }'
  jq -n --arg k "$1" --rawfile q "$TMP/q.graphql" '{query:$q, variables:{k:$k}}' > "$TMP/p.json"
  linear_gql "$TMP/p.json" > "$TMP/r.json"
  linear_check "$TMP/r.json" || return 1
  local uuid; uuid=$(jq -r '.data.teams.nodes[0].id // empty' "$TMP/r.json")
  [ -z "$uuid" ] && { echo "linear: no team with key '$1'. Run: /linear teams" >&2; return 1; }
  echo "$uuid"
}
```

Priority values: `0` none, `1` urgent, `2` high, `3` medium, `4` low.

## `configure` — interactive setup

Prompt for profile name, then the API key with `read -s` (never echoed).
Validate before saving; refuse to save an invalid key.

```bash
read -r -p "Profile name [default]: " P; P="${P:-default}"
read -r -s -p "Linear API key (lin_api_...): " KEY; echo
read -r -p "Default team key (e.g. ENG), optional: " TEAM

case "$KEY" in lin_api_*) ;; *) echo "Warning: key does not start with lin_api_" >&2 ;; esac

lq 'query{ viewer{ id name email } }'
jq -n --rawfile q "$TMP/q.graphql" '{query:$q}' > "$TMP/p.json"
CTT_API_KEY="$KEY" linear_gql "$TMP/p.json" > "$TMP/r.json"
linear_check "$TMP/r.json" || { echo "Key rejected — nothing saved." >&2; return 1; }

jq -r '"Authenticated as \(.data.viewer.name) <\(.data.viewer.email)>"' "$TMP/r.json"
ctt_save_profile linear "$P" "api_key=$KEY" ${TEAM:+"default_team=$TEAM"}
echo "Saved profile [$P] with key $(ctt_mask "$KEY")"
```

## `profile list|use|current|remove`

See `lib/credentials.sh` — `ctt_list_profiles linear`, `ctt_use_profile linear <p>`,
`ctt_active_profile linear`, `ctt_remove_profile linear <p>`. `current` prints the
profile name plus `$(ctt_mask "$CTT_API_KEY")`, never the key.

## Read verbs

### `me` — who this key belongs to

```bash
lq 'query{ viewer{ id name email admin } }'
jq -n --rawfile q "$TMP/q.graphql" '{query:$q}' > "$TMP/p.json"
linear_gql "$TMP/p.json" > "$TMP/r.json" && linear_check "$TMP/r.json" \
  && jq -r '.data.viewer | "\(.name)\t\(.email)\tadmin=\(.admin)"' "$TMP/r.json"
```

### `teams` — teams in the workspace

```bash
lq 'query{ teams(first:100){ nodes{ key name id } } }'
jq -n --rawfile q "$TMP/q.graphql" '{query:$q}' > "$TMP/p.json"
linear_gql "$TMP/p.json" > "$TMP/r.json" && linear_check "$TMP/r.json" \
  && jq -r '.data.teams.nodes[] | "\(.key)\t\(.name)\t\(.id)"' "$TMP/r.json"
```

### `states [<teamKey>]` — workflow states (needed for `update --state`)

```bash
K="${1:-$CTT_DEFAULT_TEAM}"
lq 'query($k:String!){ workflowStates(filter:{team:{key:{eq:$k}}}, first:50){
      nodes{ id name type position } } }'
jq -n --arg k "$K" --rawfile q "$TMP/q.graphql" '{query:$q, variables:{k:$k}}' > "$TMP/p.json"
linear_gql "$TMP/p.json" > "$TMP/r.json" && linear_check "$TMP/r.json" \
  && jq -r '.data.workflowStates.nodes | sort_by(.position)[] | "\(.name)\t\(.type)\t\(.id)"' "$TMP/r.json"
```

### `issues [--team K] [--state NAME] [--assignee me] [--limit N]`

Filters compose; omit what the user did not ask for. Default limit 25 — never
page without an explicit request (2,500 req/h).

```bash
LIMIT="${LIMIT:-25}"
FILTER=$(jq -n --arg team "$TEAM" --arg state "$STATE" --argjson mine "${MINE:-false}" '
  {}
  | if $team  != "" then .team     = {key:{eq:$team}}   else . end
  | if $state != "" then .state    = {name:{eq:$state}} else . end
  | if $mine       then .assignee  = {isMe:{eq:true}}   else . end')

lq 'query($f:IssueFilter, $n:Int!, $after:String){
      issues(filter:$f, first:$n, after:$after, orderBy:updatedAt){
        nodes{ identifier title priority url updatedAt
               state{ name } assignee{ displayName } }
        pageInfo{ hasNextPage endCursor } } }'
jq -n --argjson f "$FILTER" --argjson n "$LIMIT" --rawfile q "$TMP/q.graphql" \
  '{query:$q, variables:{f:$f, n:$n}}' > "$TMP/p.json"
linear_gql "$TMP/p.json" > "$TMP/r.json" && linear_check "$TMP/r.json" \
  && jq -r '.data.issues.nodes[] |
      "\(.identifier)\t\(.state.name)\t\(.assignee.displayName // "—")\t\(.title)"' "$TMP/r.json"
```

More pages: pass `.data.issues.pageInfo.endCursor` back as `$after`, and only
while `hasNextPage` is true.

### `issue <ENG-123|url>` — full detail

`issue(id:)` accepts the human identifier as well as the UUID.

```bash
ID=$(lin_id "$1")
lq 'query($id:String!){ issue(id:$id){
      identifier title description priority url createdAt updatedAt
      state{ name type } assignee{ displayName email } creator{ displayName }
      team{ key name } project{ name } labels{ nodes{ name } }
      comments(first:50){ nodes{ body createdAt user{ displayName } } } } }'
jq -n --arg id "$ID" --rawfile q "$TMP/q.graphql" '{query:$q, variables:{id:$id}}' > "$TMP/p.json"
linear_gql "$TMP/p.json" > "$TMP/r.json" && linear_check "$TMP/r.json"
```

Format: identifier + title, team/state/assignee/priority, labels, URL, then the
markdown description as-is, then comments oldest-first.

### `search <query>`

```bash
printf '%s' "$QUERY" > "$TMP/term.txt"
lq 'query($t:String!, $n:Int!){ searchIssues(term:$t, first:$n){
      nodes{ identifier title url state{ name } team{ key } } } }'
jq -n --rawfile t "$TMP/term.txt" --argjson n "${LIMIT:-25}" --rawfile q "$TMP/q.graphql" \
  '{query:$q, variables:{t:$t, n:$n}}' > "$TMP/p.json"
linear_gql "$TMP/p.json" > "$TMP/r.json" && linear_check "$TMP/r.json" \
  && jq -r '.data.searchIssues.nodes[] | "\(.identifier)\t\(.state.name)\t\(.title)"' "$TMP/r.json"
```

The term goes through `--rawfile` like every other user string, so a Vietnamese
or emoji search works.

### `projects [--team K]`

`Project` has **no `state` field** — the status is an object, `status { name }`.
Team scoping goes through `accessibleTeams`, not a `team` field.

```bash
FILTER=$(jq -n --arg team "$TEAM" '
  {} | if $team != "" then .accessibleTeams = {some:{key:{eq:$team}}} else . end')
lq 'query($f:ProjectFilter, $n:Int!){
      projects(filter:$f, first:$n){
        nodes{ name progress targetDate url health status{ name } } } }'
jq -n --argjson f "$FILTER" --argjson n "${LIMIT:-25}" --rawfile q "$TMP/q.graphql" \
  '{query:$q, variables:{f:$f, n:$n}}' > "$TMP/p.json"
linear_gql "$TMP/p.json" > "$TMP/r.json" && linear_check "$TMP/r.json" \
  && jq -r '.data.projects.nodes[] | "\(.name)\t\(.status.name)\t\((.progress*100|floor))%\t\(.targetDate // "—")"' "$TMP/r.json"
```

### `cycles [<teamKey>]`

```bash
K="${1:-$CTT_DEFAULT_TEAM}"
lq 'query($k:String!){ cycles(filter:{team:{key:{eq:$k}}}, first:10){
      nodes{ number name startsAt endsAt progress } } }'
jq -n --arg k "$K" --rawfile q "$TMP/q.graphql" '{query:$q, variables:{k:$k}}' > "$TMP/p.json"
linear_gql "$TMP/p.json" > "$TMP/r.json" && linear_check "$TMP/r.json" \
  && jq -r '.data.cycles.nodes[] | "#\(.number)\t\(.name // "—")\t\(.startsAt[0:10]) → \(.endsAt[0:10])"' "$TMP/r.json"
```

`FEATURE_NOT_ACCESSIBLE` here means the workspace plan has cycles disabled.

## Write verbs

All three read their text from a file and send it as a GraphQL **variable**.
Gate with `ctt_confirm` when the profile sets `require_confirm`, then
`ctt_audit_log`.

### `create <teamKey> <title> [description]`

```bash
[ "${CTT_REQUIRE_CONFIRM:-}" = "true" ] && { ctt_confirm "Create issue in $1 on $CTT_PROFILE?" || return 1; }
TEAM_UUID=$(lin_team_uuid "$1") || return 1

printf '%s' "$TITLE" > "$TMP/title.txt"
printf '%s' "$DESC"  > "$TMP/desc.txt"       # empty file is fine
lq 'mutation($t:String!, $d:String, $team:String!){
      issueCreate(input:{title:$t, description:$d, teamId:$team}){
        success issue{ identifier url title } } }'
jq -an --arg team "$TEAM_UUID" \
       --rawfile t "$TMP/title.txt" --rawfile d "$TMP/desc.txt" \
       --rawfile q "$TMP/q.graphql" \
       '{query:$q, variables:{t:$t, d:(if $d=="" then null else $d end), team:$team}}' > "$TMP/p.json"
linear_gql "$TMP/p.json" > "$TMP/r.json" && linear_check "$TMP/r.json" || return 1
NEW=$(jq -r '.data.issueCreate.issue.identifier' "$TMP/r.json")
jq -r '.data.issueCreate.issue | "\(.identifier)\t\(.url)"' "$TMP/r.json"
ctt_audit_log linear "created $NEW in team $1"
```

Then read it back — `success:true` does not prove the text survived:

```bash
lq 'query($id:String!){ issue(id:$id){ title description } }'
jq -n --arg id "$NEW" --rawfile q "$TMP/q.graphql" '{query:$q, variables:{id:$id}}' > "$TMP/p.json"
linear_gql "$TMP/p.json" > "$TMP/r.json" && jq -r '.data.issue.title' "$TMP/r.json"
```

### `comment <ENG-123|url> <text>`

```bash
ID=$(lin_id "$1")
[ "${CTT_REQUIRE_CONFIRM:-}" = "true" ] && { ctt_confirm "Comment on $ID as $CTT_PROFILE?" || return 1; }

cat > "$TMP/body.txt" <<'BODY'
<comment text — any characters, any number of lines>
BODY
lq 'mutation($id:String!, $b:String!){
      commentCreate(input:{issueId:$id, body:$b}){ success comment{ id url } } }'
jq -an --arg id "$ID" --rawfile b "$TMP/body.txt" --rawfile q "$TMP/q.graphql" \
  '{query:$q, variables:{id:$id, b:$b}}' > "$TMP/p.json"
linear_gql "$TMP/p.json" > "$TMP/r.json" && linear_check "$TMP/r.json" || return 1
jq -r '.data.commentCreate.comment.url' "$TMP/r.json"
ctt_audit_log linear "commented on $ID"
```

Mandatory read-back — fetch the newest comment and look at it:

```bash
lq 'query($id:String!){ issue(id:$id){ comments(last:1){ nodes{ body } } } }'
jq -n --arg id "$ID" --rawfile q "$TMP/q.graphql" '{query:$q, variables:{id:$id}}' > "$TMP/p.json"
linear_gql "$TMP/p.json" > "$TMP/r.json" && jq -r '.data.issue.comments.nodes[0].body' "$TMP/r.json"
```

### `update <ENG-123|url> [--state NAME] [--assignee me|<email>] [--priority 0-4]`

`issueUpdate(id:)` accepts `ENG-123`. `--state` needs a state **UUID**, so
resolve the name through `states <teamKey>` first; same for `--assignee`.

```bash
ID=$(lin_id "$1")
[ "${CTT_REQUIRE_CONFIRM:-}" = "true" ] && { ctt_confirm "Update $ID on $CTT_PROFILE?" || return 1; }

INPUT=$(jq -n --arg s "$STATE_UUID" --arg a "$ASSIGNEE_UUID" --argjson p "${PRIORITY:-null}" '
  {} | if $s != ""   then .stateId    = $s else . end
     | if $a != ""   then .assigneeId = $a else . end
     | if $p != null then .priority   = $p else . end')
[ "$INPUT" = "{}" ] && { echo "linear: nothing to update" >&2; return 1; }

lq 'mutation($id:String!, $in:IssueUpdateInput!){
      issueUpdate(id:$id, input:$in){
        success issue{ identifier priority state{ name } assignee{ displayName } } } }'
jq -n --arg id "$ID" --argjson in "$INPUT" --rawfile q "$TMP/q.graphql" \
  '{query:$q, variables:{id:$id, in:$in}}' > "$TMP/p.json"
linear_gql "$TMP/p.json" > "$TMP/r.json" && linear_check "$TMP/r.json" || return 1
jq -r '.data.issueUpdate.issue | "\(.identifier)\t\(.state.name)\t\(.assignee.displayName // "—")\tP\(.priority)"' "$TMP/r.json"
ctt_audit_log linear "updated $ID fields: $(echo "$INPUT" | jq -r 'keys | join(",")')"
```

The audit line records field **names** only — never the values.

A title or description change carries text, so it goes through `--rawfile` and
a read-back exactly like `create`.

Assignee lookup by email:

```bash
lq 'query($e:String!){ users(filter:{email:{eq:$e}}, first:1){ nodes{ id displayName } } }'
```

`--assignee me` → take `.data.viewer.id` from the `me` recipe.

### `archive <ENG-123|url>` — reversible removal

Always confirmed, regardless of `require_confirm`.

```bash
ID=$(lin_id "$1")
ctt_confirm "Archive $ID on $CTT_PROFILE?" || return 1
lq 'mutation($id:String!){ issueArchive(id:$id){ success } }'
jq -n --arg id "$ID" --rawfile q "$TMP/q.graphql" '{query:$q, variables:{id:$id}}' > "$TMP/p.json"
linear_gql "$TMP/p.json" > "$TMP/r.json" && linear_check "$TMP/r.json" || return 1
jq -r '"archived: \(.data.issueArchive.success)"' "$TMP/r.json"
ctt_audit_log linear "archived $ID"
```

There is deliberately no `delete` recipe. Unarchive is `issueUnarchive(id:)`.

## Errors worth recognising

| Symptom | Cause |
|---|---|
| `AUTHENTICATION_ERROR` | key revoked, or `Bearer` wrongly prefixed |
| HTTP 400 + `RATELIMITED` | 2,500 req/h or 3M complexity points/h exhausted |
| `Query is too complex` | over 10,000 points — cut page sizes and nesting |
| `FEATURE_NOT_ACCESSIBLE` | workspace plan lacks that feature (e.g. cycles) |
| `entity not found` on `create` | `teamId` was a team key, not a UUID |

## Verifying a field name without a key

Linear answers **introspection queries unauthenticated** (600 req/h per IP), so
a doubtful field or filter can be checked before writing a recipe:

```bash
curl -s -X POST -H "Content-Type: application/json" \
  -d '{"query":"query{ __type(name:\"IssueFilter\"){ inputFields{ name type{ name } } } }"}' \
  https://api.linear.app/graphql | jq -r '.data.__type.inputFields[].name'
```

Keep introspection queries narrow — a full `__schema` dump costs 16,384 points
and is rejected by the 10,000-point cap.

Validation also runs **before** authentication, so any document can be checked
without a key: send it unauthenticated and read the error code. An
`AUTHENTICATION_ERROR` means the document is schema-valid;
`GRAPHQL_VALIDATION_FAILED` names the bad field or filter.

All 17 documents in this file were validated that way on 2026-09-08. Two traps
it caught: `Project.state` does not exist (it is `status { name }`), and
projects are scoped to a team through `accessibleTeams`, not `team`.
