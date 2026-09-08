# /linear — recipes (load on demand)

> Loaded by SKILL.md only when the user invokes a specific dispatch verb.
> Endpoint: `https://api.linear.app/graphql` (POST only, one URL for everything).

**Every verb below is a shell function.** Define it, then call it. That is not
cosmetic: `return` outside a function is a bash error that prints
``can only `return' from a function or sourced script`` and lets execution fall
through to the next line. Pasted as a bare top-level block, a declined
confirmation or a failed lookup would not stop the recipe — the mutation would
still be sent and the audit line still written.

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

# Fail loudly on every failure shape. $1 = response file. Returns 1 on failure.
#
# Linear DOES map errors to real HTTP statuses — 401 for AUTHENTICATION_ERROR,
# 400 for GRAPHQL_VALIDATION_FAILED / INPUT_ERROR / RATELIMITED — and puts the
# diagnosis in the body of those non-2xx responses. linear_gql uses `curl -s`
# without `-f`, so the body always arrives and is always worth reading.
# A plain `jq -e '.errors' 2>/dev/null` is NOT enough: when the body is not
# JSON at all (proxy or CDN HTML, a truncated read, an empty file) jq exits
# non-zero, the `if` goes false, and a total failure is waved through as success.
linear_check() {
  if ! jq -e . "$1" >/dev/null 2>&1; then
    echo "linear: response is not JSON (proxy error page, truncated or empty body):" >&2
    head -c 300 "$1" >&2; echo >&2
    return 1
  fi
  if jq -e '.errors and (.errors | length > 0)' "$1" >/dev/null 2>&1; then
    jq -r '.errors[] | "linear: \(.extensions.code // "ERROR"): \(.message)"' "$1" >&2
    if jq -e '[.errors[].extensions.code] | index("RATELIMITED")' "$1" >/dev/null 2>&1; then
      echo "linear: rate limited — one of the two independent hourly budgets is spent:" >&2
      echo "  2,500 requests/h or 3,000,000 complexity points/h (per user, API key)." >&2
      echo "  Re-run with 'curl -D -' and compare x-ratelimit-requests-remaining against" >&2
      echo "  x-ratelimit-complexity-remaining; the matching *-reset header is UTC epoch ms." >&2
      echo "  Complexity exhaustion is fixed by smaller page sizes and less nesting," >&2
      echo "  not by making fewer calls. Do not retry in a loop." >&2
    fi
    return 1
  fi
  # A non-GraphQL error envelope, e.g. a malformed request body.
  if jq -e 'has("error") and (has("data") | not)' "$1" >/dev/null 2>&1; then
    jq -r '"linear: \(.code // "error"): \(.error)"' "$1" >&2
    return 1
  fi
  return 0
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

# Gate every write verb. Call it FIRST, before building any payload:
#   lin_guard_write "Create issue in ENG" || return 1
# Written as if/fi rather than "[ cond ] && { ...; }" on purpose: that idiom
# returns the test's exit status when the condition is false, so as the last
# line of a function it makes a successful no-op look like a failure.
lin_guard_write() {
  if [ "${CTT_READ_ONLY:-}" = "true" ]; then
    echo "linear: profile '$CTT_PROFILE' is read_only. Refusing: $1" >&2
    return 1
  fi
  if [ "${CTT_REQUIRE_CONFIRM:-}" = "true" ]; then
    ctt_confirm "$1 on $CTT_PROFILE?" || return 1
  fi
  return 0
}

# Resolve a team key (ENG) to its UUID — issueCreate needs the UUID.
lin_team_uuid() {
  lq 'query($k:String!){ teams(filter:{key:{eq:$k}}, first:1){ nodes{ id key name } } }'
  jq -n --arg k "$1" --rawfile q "$TMP/q.graphql" '{query:$q, variables:{k:$k}}' > "$TMP/p.json"
  linear_gql "$TMP/p.json" > "$TMP/r.json"
  linear_check "$TMP/r.json" || return 1
  local uuid; uuid=$(jq -r '.data.teams.nodes[0].id // empty' "$TMP/r.json")
  if [ -z "$uuid" ]; then
    echo "linear: no team with key '$1'. Run: /linear teams" >&2
    return 1
  fi
  echo "$uuid"
}
```

Priority values: `0` none, `1` urgent, `2` high, `3` medium, `4` low.

## `configure` — interactive setup

Before prompting, tell the user which permissions to tick when they create the
key and steer them to the narrowest one — see the permission table in SKILL.md.
Read-only is the right default for anyone who only queries.

```bash
linear_configure() {
  local P KEY TEAM RO
  read -r -p "Profile name [default]: " P; P="${P:-default}"
  read -r -s -p "Linear API key (lin_api_...): " KEY; echo
  read -r -p "Default team key (e.g. ENG), optional: " TEAM
  read -r -p "Is this a Read-only key? [Y/n]: " RO

  case "$KEY" in lin_api_*) ;; *) echo "Warning: key does not start with lin_api_" >&2 ;; esac

  lq 'query{ viewer{ id name email } }'
  jq -n --rawfile q "$TMP/q.graphql" '{query:$q}' > "$TMP/p.json"
  CTT_API_KEY="$KEY" linear_gql "$TMP/p.json" > "$TMP/r.json"
  linear_check "$TMP/r.json" || { echo "Key rejected — nothing saved." >&2; return 1; }

  jq -r '"Authenticated as \(.data.viewer.name) <\(.data.viewer.email)>"' "$TMP/r.json"

  local FIELDS=("api_key=$KEY")
  [ -n "$TEAM" ] && FIELDS+=("default_team=$TEAM")
  case "$RO" in [Nn]*) ;; *) FIELDS+=("read_only=true") ;; esac
  ctt_save_profile linear "$P" "${FIELDS[@]}"
  echo "Saved profile [$P] with key $(ctt_mask "$KEY")"
}
linear_configure
```

The `return 1` after a rejected key is why this is a function. As a bare block
it would print "nothing saved", carry on, print `Authenticated as null <null>`,
and write the rejected key to `~/.linear/credentials`.

`viewer` succeeds on a Read-only key, so a successful validation proves the key
is live — **not** that it can write. The API exposes no query that reads a key's
own permissions back (there is no `apiKeys` field on the query root), so
`read_only` records what the user says here. When a later write fails with an
authorization error the key simply lacks that permission: report it, and do not
suggest widening the key to Write or Admin unless the user asks.

## `profile list|use|current|remove`

See `lib/credentials.sh` — `ctt_list_profiles linear`, `ctt_use_profile linear <p>`,
`ctt_active_profile linear`, `ctt_remove_profile linear <p>`. `current` prints the
profile name plus `$(ctt_mask "$CTT_API_KEY")`, never the key.

## Read verbs

### `me` — who this key belongs to

```bash
linear_me() {
  lq 'query{ viewer{ id name email admin } }'
  jq -n --rawfile q "$TMP/q.graphql" '{query:$q}' > "$TMP/p.json"
  linear_gql "$TMP/p.json" > "$TMP/r.json"
  linear_check "$TMP/r.json" || return 1
  jq -r '.data.viewer | "\(.name)\t\(.email)\tadmin=\(.admin)"' "$TMP/r.json"
}
linear_me
```

### `teams` — teams in the workspace

```bash
linear_teams() {
  lq 'query{ teams(first:100){ nodes{ key name id } } }'
  jq -n --rawfile q "$TMP/q.graphql" '{query:$q}' > "$TMP/p.json"
  linear_gql "$TMP/p.json" > "$TMP/r.json"
  linear_check "$TMP/r.json" || return 1
  jq -r '.data.teams.nodes[] | "\(.key)\t\(.name)\t\(.id)"' "$TMP/r.json"
}
linear_teams
```

### `states [<teamKey>]` — workflow states (needed for `update --state`)

```bash
linear_states() {
  local K="${1:-$CTT_DEFAULT_TEAM}"
  if [ -z "$K" ]; then echo "linear: no team key. Pass one or set default_team." >&2; return 1; fi
  lq 'query($k:String!){ workflowStates(filter:{team:{key:{eq:$k}}}, first:50){
        nodes{ id name type position } } }'
  jq -n --arg k "$K" --rawfile q "$TMP/q.graphql" '{query:$q, variables:{k:$k}}' > "$TMP/p.json"
  linear_gql "$TMP/p.json" > "$TMP/r.json"
  linear_check "$TMP/r.json" || return 1
  jq -r '.data.workflowStates.nodes | sort_by(.position)[] | "\(.name)\t\(.type)\t\(.id)"' "$TMP/r.json"
}
linear_states "$TEAM_KEY"
```

### `issues [--team K] [--state NAME] [--assignee me] [--limit N]`

Filters compose; omit what the user did not ask for. Default limit 25 — never
page without an explicit request.

```bash
linear_issues() {
  local LIMIT="${LIMIT:-25}" FILTER
  FILTER=$(jq -n --arg team "${TEAM:-}" --arg state "${STATE:-}" --argjson mine "${MINE:-false}" '
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
  linear_gql "$TMP/p.json" > "$TMP/r.json"
  linear_check "$TMP/r.json" || return 1
  jq -r '.data.issues.nodes[] |
    "\(.identifier)\t\(.state.name)\t\(.assignee.displayName // "—")\t\(.title)"' "$TMP/r.json"
  jq -r 'if .data.issues.pageInfo.hasNextPage
         then "-- more available; next cursor: \(.data.issues.pageInfo.endCursor)"
         else empty end' "$TMP/r.json"
}
linear_issues
```

More pages: pass `endCursor` back as `$after`, and only while `hasNextPage` is
true. The cursor line above exists so a truncated list never looks complete.

### `issue <ENG-123|url>` — full detail

`issue(id:)` accepts the human identifier as well as the UUID.

```bash
linear_issue() {
  local ID; ID=$(lin_id "$1")
  lq 'query($id:String!){ issue(id:$id){
        identifier title description priority url createdAt updatedAt
        state{ name type } assignee{ displayName email } creator{ displayName }
        team{ key name } project{ name } labels{ nodes{ name } }
        comments(first:50){ nodes{ body createdAt user{ displayName } } } } }'
  jq -n --arg id "$ID" --rawfile q "$TMP/q.graphql" '{query:$q, variables:{id:$id}}' > "$TMP/p.json"
  linear_gql "$TMP/p.json" > "$TMP/r.json"
  linear_check "$TMP/r.json" || return 1
  cat "$TMP/r.json"
}
linear_issue "$ARG"
```

Format: identifier + title, team/state/assignee/priority, labels, URL, then the
markdown description as-is, then comments sorted by `createdAt`. Do not assume
the connection's order — sort on the timestamp you selected.

### `search <query>`

```bash
linear_search() {
  printf '%s' "$1" > "$TMP/term.txt"
  lq 'query($t:String!, $n:Int!){ searchIssues(term:$t, first:$n){
        nodes{ identifier title url state{ name } team{ key } } } }'
  jq -n --rawfile t "$TMP/term.txt" --argjson n "${LIMIT:-25}" --rawfile q "$TMP/q.graphql" \
    '{query:$q, variables:{t:$t, n:$n}}' > "$TMP/p.json"
  linear_gql "$TMP/p.json" > "$TMP/r.json"
  linear_check "$TMP/r.json" || return 1
  jq -r '.data.searchIssues.nodes[] | "\(.identifier)\t\(.state.name)\t\(.title)"' "$TMP/r.json"
}
linear_search "$QUERY"
```

The term goes through `--rawfile` like every other user string, so a Vietnamese
or emoji search works.

### `projects [--team K]`

`Project.state` still exists but is **deprecated** (`Use project.status instead`)
and returns a plain `String`, not an object. Select `status { name }`. Team
scoping goes through `accessibleTeams`, not a `team` field — `ProjectFilter` has
no `team` input.

```bash
linear_projects() {
  local FILTER
  FILTER=$(jq -n --arg team "${TEAM:-}" '
    {} | if $team != "" then .accessibleTeams = {some:{key:{eq:$team}}} else . end')
  lq 'query($f:ProjectFilter, $n:Int!){
        projects(filter:$f, first:$n){
          nodes{ name progress targetDate url health status{ name } } } }'
  jq -n --argjson f "$FILTER" --argjson n "${LIMIT:-25}" --rawfile q "$TMP/q.graphql" \
    '{query:$q, variables:{f:$f, n:$n}}' > "$TMP/p.json"
  linear_gql "$TMP/p.json" > "$TMP/r.json"
  linear_check "$TMP/r.json" || return 1
  jq -r '.data.projects.nodes[] |
    "\(.name)\t\(.status.name)\t\((.progress*100|floor))%\t\(.targetDate // "—")"' "$TMP/r.json"
}
linear_projects
```

### `cycles [<teamKey>]`

```bash
linear_cycles() {
  local K="${1:-$CTT_DEFAULT_TEAM}"
  if [ -z "$K" ]; then echo "linear: no team key. Pass one or set default_team." >&2; return 1; fi
  lq 'query($k:String!){ cycles(filter:{team:{key:{eq:$k}}}, first:10){
        nodes{ number name startsAt endsAt progress } } }'
  jq -n --arg k "$K" --rawfile q "$TMP/q.graphql" '{query:$q, variables:{k:$k}}' > "$TMP/p.json"
  linear_gql "$TMP/p.json" > "$TMP/r.json"
  linear_check "$TMP/r.json" || return 1
  jq -r '.data.cycles.nodes[] |
    "#\(.number)\t\(.name // "—")\t\(.startsAt[0:10]) → \(.endsAt[0:10])"' "$TMP/r.json"
}
linear_cycles "$TEAM_KEY"
```

`FEATURE_NOT_ACCESSIBLE` here means the workspace plan has cycles disabled.

## Write verbs

Each reads its text from a file and sends it as a GraphQL **variable**.
`lin_guard_write` refuses on a `read_only` profile and confirms when the profile
sets `require_confirm`.

### `create <teamKey> <title> [description]`

```bash
linear_create() {
  local TEAM_KEY="$1" TITLE="$2" DESC="${3:-}" TEAM_UUID NEW
  lin_guard_write "Create issue in $TEAM_KEY" || return 1
  TEAM_UUID=$(lin_team_uuid "$TEAM_KEY") || return 1

  printf '%s' "$TITLE" > "$TMP/title.txt"
  printf '%s' "$DESC"  > "$TMP/desc.txt"       # empty file is fine
  lq 'mutation($t:String!, $d:String, $team:String!){
        issueCreate(input:{title:$t, description:$d, teamId:$team}){
          success issue{ id identifier url title } } }'
  jq -an --arg team "$TEAM_UUID" \
         --rawfile t "$TMP/title.txt" --rawfile d "$TMP/desc.txt" \
         --rawfile q "$TMP/q.graphql" \
         '{query:$q, variables:{t:$t, d:(if $d=="" then null else $d end), team:$team}}' > "$TMP/p.json"
  linear_gql "$TMP/p.json" > "$TMP/r.json"
  linear_check "$TMP/r.json" || return 1
  NEW=$(jq -r '.data.issueCreate.issue.identifier' "$TMP/r.json")
  jq -r '.data.issueCreate.issue | "\(.identifier)\t\(.url)"' "$TMP/r.json"
  ctt_audit_log linear "created $NEW in team $TEAM_KEY"

  # Read back by identifier. success:true does not prove the text survived.
  lq 'query($id:String!){ issue(id:$id){ title description } }'
  jq -n --arg id "$NEW" --rawfile q "$TMP/q.graphql" '{query:$q, variables:{id:$id}}' > "$TMP/p.json"
  linear_gql "$TMP/p.json" > "$TMP/r.json"
  linear_check "$TMP/r.json" || return 1
  jq -r '.data.issue.title' "$TMP/r.json"
}
linear_create "$TEAM_KEY" "$TITLE" "$DESC"
```

### `comment <ENG-123|url> <text>`

```bash
linear_comment() {
  local ID CID
  ID=$(lin_id "$1")
  lin_guard_write "Comment on $ID" || return 1

  cat > "$TMP/body.txt" <<'BODY'
<comment text — any characters, any number of lines>
BODY
  lq 'mutation($id:String!, $b:String!){
        commentCreate(input:{issueId:$id, body:$b}){ success comment{ id url } } }'
  jq -an --arg id "$ID" --rawfile b "$TMP/body.txt" --rawfile q "$TMP/q.graphql" \
    '{query:$q, variables:{id:$id, b:$b}}' > "$TMP/p.json"
  linear_gql "$TMP/p.json" > "$TMP/r.json"
  linear_check "$TMP/r.json" || return 1
  CID=$(jq -r '.data.commentCreate.comment.id' "$TMP/r.json")   # capture BEFORE r.json is reused
  jq -r '.data.commentCreate.comment.url' "$TMP/r.json"
  ctt_audit_log linear "commented on $ID"

  # Read back BY ID, never by position. Do not use comments(last:1) for this:
  # the connection's sort direction is not documented, so "last" is not
  # reliably the comment you just wrote.
  lq 'query($id:String!){ comment(id:$id){ body } }'
  jq -n --arg id "$CID" --rawfile q "$TMP/q.graphql" '{query:$q, variables:{id:$id}}' > "$TMP/p.json"
  linear_gql "$TMP/p.json" > "$TMP/r.json"
  linear_check "$TMP/r.json" || return 1
  jq -r '.data.comment.body' "$TMP/r.json"
}
linear_comment "$ARG"
```

### `update <ENG-123|url> [--state NAME] [--assignee me|<email>] [--priority 0-4]`

`issueUpdate(id:)` accepts `ENG-123`. `--state` needs a state **UUID**, so
resolve the name through `states <teamKey>` first; same for `--assignee`.

```bash
linear_update() {
  local ID INPUT
  ID=$(lin_id "$1")
  lin_guard_write "Update $ID" || return 1

  INPUT=$(jq -n --arg s "${STATE_UUID:-}" --arg a "${ASSIGNEE_UUID:-}" --argjson p "${PRIORITY:-null}" '
    {} | if $s != ""   then .stateId    = $s else . end
       | if $a != ""   then .assigneeId = $a else . end
       | if $p != null then .priority   = $p else . end')
  if [ "$INPUT" = "{}" ]; then echo "linear: nothing to update" >&2; return 1; fi

  lq 'mutation($id:String!, $in:IssueUpdateInput!){
        issueUpdate(id:$id, input:$in){
          success issue{ identifier priority state{ name } assignee{ displayName } } } }'
  jq -n --arg id "$ID" --argjson in "$INPUT" --rawfile q "$TMP/q.graphql" \
    '{query:$q, variables:{id:$id, in:$in}}' > "$TMP/p.json"
  linear_gql "$TMP/p.json" > "$TMP/r.json"
  linear_check "$TMP/r.json" || return 1
  jq -r '.data.issueUpdate.issue |
    "\(.identifier)\t\(.state.name)\t\(.assignee.displayName // "—")\tP\(.priority)"' "$TMP/r.json"
  ctt_audit_log linear "updated $ID fields: $(echo "$INPUT" | jq -r 'keys | join(",")')"
}
linear_update "$ARG"
```

The audit line records field **names** only, never the values. A title or
description change carries text, so it goes through `--rawfile` and a read-back
exactly like `create`.

Assignee lookup by email:

```bash
lq 'query($e:String!){ users(filter:{email:{eq:$e}}, first:1){ nodes{ id displayName } } }'
```

`--assignee me` → take `.data.viewer.id` from the `me` recipe.

### `archive <ENG-123|url>` — reversible removal

Always confirmed, regardless of `require_confirm`. The `read_only` check comes
first so a read profile refuses before any prompt is shown.

```bash
linear_archive() {
  local ID; ID=$(lin_id "$1")
  if [ "${CTT_READ_ONLY:-}" = "true" ]; then
    echo "linear: profile '$CTT_PROFILE' is read_only. Refusing to archive $ID" >&2
    return 1
  fi
  ctt_confirm "Archive $ID on $CTT_PROFILE?" || return 1
  lq 'mutation($id:String!){ issueArchive(id:$id){ success } }'
  jq -n --arg id "$ID" --rawfile q "$TMP/q.graphql" '{query:$q, variables:{id:$id}}' > "$TMP/p.json"
  linear_gql "$TMP/p.json" > "$TMP/r.json"
  linear_check "$TMP/r.json" || return 1
  jq -r '"archived: \(.data.issueArchive.success)"' "$TMP/r.json"
  ctt_audit_log linear "archived $ID"
}
linear_archive "$ARG"
```

The audit line is inside the function and after `linear_check`, so a refused or
failed archive never writes a false "archived" record. There is deliberately no
`delete` recipe. Unarchive is `issueUnarchive(id:)`.

## Errors worth recognising

Linear returns real HTTP statuses, and the diagnosis is in the body of those
non-2xx responses. Read the body whatever the status.

| Status | Code | Cause |
|---|---|---|
| 401 | `AUTHENTICATION_ERROR` | key revoked, or `Bearer` wrongly prefixed |
| 400 | `GRAPHQL_VALIDATION_FAILED` | bad field or filter; the message names it |
| 400 | `INPUT_ERROR` | malformed variables, or a query over the complexity cap |
| 400 | `RATELIMITED` | the 2,500 req/h **or** the 3M complexity-points/h budget is spent |
| 200 | `FEATURE_NOT_ACCESSIBLE` | workspace plan lacks that feature (e.g. cycles) |
| 200 | `errors` present | partial field-level failure; `data` may be partly filled |
| — | `entity not found` on `create` | `teamId` was a team key, not a UUID |

Rate-limit headers (`x-ratelimit-requests-remaining`,
`x-ratelimit-complexity-remaining`, matching `*-reset` in UTC epoch ms, and
`x-complexity` for the call just made) ride on successful responses. A 401
carries none of them, so do not look for them when auth failed.

## Verifying a field name without a key

Linear answers **introspection unauthenticated**, and it runs document
**validation before authentication**. Both facts make a doubtful field checkable
for free:

```bash
curl -s -X POST -H "Content-Type: application/json" \
  -d '{"query":"query{ __type(name:\"IssueFilter\"){ inputFields{ name type{ name } } } }"}' \
  https://api.linear.app/graphql | jq -r '.data.__type.inputFields[].name'
```

To validate a whole document, send it unauthenticated and read the error code:
`AUTHENTICATION_ERROR` (401) means the document is schema-valid;
`GRAPHQL_VALIDATION_FAILED` (400) names the bad field or filter.

Keep introspection queries narrow for **size**, not for cost. A canonical full
`IntrospectionQuery` succeeds and scores only a couple of hundred complexity
points against the 10,000-point per-query cap, but it returns megabytes covering
more than a thousand types. Cost only bites on badly shaped queries: asking for
every query-root field with its args and nested `ofType` chain was rejected here
at 16,384 points, so shape the query, do not dump the schema.

All 17 documents in this file were validated that way on 2026-09-08. The trap it
caught: `ProjectFilter` has no `team` input field, so projects scope to a team
through `accessibleTeams`. It could **not** have caught `Project.state`, which is
still a valid field — deprecated in favour of `status { name }`, but accepted by
validation. Deprecation is not a validation error, so read `isDeprecated` from
introspection when a field looks suspicious.
