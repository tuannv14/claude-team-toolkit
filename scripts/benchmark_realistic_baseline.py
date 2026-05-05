#!/usr/bin/env python3
"""
benchmark_realistic_baseline.py — measure REAL "without skill" task cost
by tokenizing actual sample responses Claude would generate ad-hoc.

Each sample below is a typical response Claude would produce for a common
task PER SERVICE without having a skill loaded. Hand-written to match
Claude's style: explain + generate command + format output. Tokens are
counted for each, then averaged.

This replaces the heuristic estimate (body × 1.5 + retry) used in
benchmark_tokens.py with a more direct measurement.

Run: python3 scripts/benchmark_realistic_baseline.py
"""
import sys
try:
    import tiktoken
except ImportError:
    print("Install: pip install tiktoken", file=sys.stderr)
    sys.exit(1)

enc = tiktoken.get_encoding("cl100k_base")
def tok(s): return len(enc.encode(s))


# Realistic sample responses Claude would generate WITHOUT a skill, per task.
# Each entry: skill name -> list of (task description, sample_response_text)
SAMPLES = {
    "trello": [
        ("Fetch a Trello card from URL", """I'll fetch the Trello card details. The URL https://trello.com/c/AbCd1234 contains card ID `AbCd1234`. I'll use curl with your Trello API credentials.

```bash
KEY=$TRELLO_KEY  # set in your env
TOKEN=$TRELLO_TOKEN

curl -s "https://api.trello.com/1/cards/AbCd1234?key=$KEY&token=$TOKEN&fields=all&attachments=true&checklists=all&members=true&actions=commentCard&actions_limit=20&list=true&board=true" | jq '.'
```

If you don't have credentials yet, get them at:
1. API Key: https://trello.com/app-key
2. Token: click "Token" link, then "Allow"

The response will include name, description, due date, members, labels, checklists, attachments, and comments. Let me know the actual URL and I can format the output for you."""),
        ("List boards for a user", """To list your Trello boards I'll call the members/me endpoint:

```bash
curl -s "https://api.trello.com/1/members/me/boards?key=$TRELLO_KEY&token=$TRELLO_TOKEN&fields=name,url,closed" | jq -r '.[] | select(.closed==false) | "\\(.id)\\t\\(.name)\\t\\(.url)"'
```

This returns only open boards. To include archived, remove the `closed==false` filter."""),
        ("Create a new card on a list", """I'll create a card via the Trello REST API:

```bash
curl -s -X POST "https://api.trello.com/1/cards?key=$TRELLO_KEY&token=$TRELLO_TOKEN" \\
  --data-urlencode "idList=$LIST_ID" \\
  --data-urlencode "name=$TITLE" \\
  --data-urlencode "desc=$DESCRIPTION"
```

Make sure you `--data-urlencode` user input rather than interpolating directly to avoid breaking the API call on special characters."""),
    ],
    "azure-devops": [
        ("List PRs in a repo", """For Azure DevOps Services (cloud), use the REST API. For self-hosted Server, the `az` CLI doesn't work; use REST directly.

```bash
PAT="$AZDO_PAT"
AUTH=$(printf ":%s" "$PAT" | base64 -w0)
ORG="https://dev.azure.com/your-org"
PROJECT="MyProject"

curl -s -H "Authorization: Basic $AUTH" \\
  "$ORG/$PROJECT/_apis/git/repositories/MyRepo/pullrequests?searchCriteria.status=active&api-version=7.0" \\
  | jq -r '.value[] | "\\(.pullRequestId)\\t\\(.status)\\t\\(.title)"'
```

For self-hosted, use `api-version=5.1` (newer versions return VssVersionOutOfRangeException).

If you get 401, your PAT lacks "Code (Read)" scope. Generate a new PAT at <org>/_usersSettings/tokens."""),
        ("Run a WIQL query for assigned work items", """WIQL queries run against the work items REST endpoint:

```bash
WIQL='SELECT [System.Id], [System.Title], [System.State] FROM workitems WHERE [System.AssignedTo] = @Me AND [System.State] <> "Closed" ORDER BY [System.ChangedDate] DESC'

BODY=$(jq -n --arg q "$WIQL" '{query: $q}')

curl -s -X POST -H "Authorization: Basic $AUTH" -H "Content-Type: application/json" \\
  -d "$BODY" \\
  "$ORG/$PROJECT/_apis/wit/wiql?api-version=7.0"
```

The response gives you work item IDs. To get full details, follow up with /wit/workitems/{id}."""),
        ("Create a PR", """To create a pull request via REST:

```bash
BODY=$(jq -n \\
  --arg src "refs/heads/feat/my-branch" \\
  --arg tgt "refs/heads/main" \\
  --arg t "PR title" \\
  --arg d "Description" \\
  '{sourceRefName: $src, targetRefName: $tgt, title: $t, description: $d}')

curl -s -X POST -H "Authorization: Basic $AUTH" -H "Content-Type: application/json" \\
  -d "$BODY" \\
  "$ORG/$PROJECT/_apis/git/repositories/MyRepo/pullrequests?api-version=7.0"
```

Use `jq -n --arg` for the JSON body — interpolating raw strings can break on quotes/newlines."""),
    ],
    "heroku": [
        ("Set config vars on a Heroku app", """To set config vars on Heroku via Platform API v3:

```bash
KEY="$HEROKU_API_KEY"
APP="my-app"

# Build JSON body
BODY=$(jq -n '{KEY1: "value1", KEY2: "value2"}')

curl -s -X PATCH \\
  -H "Authorization: Bearer $KEY" \\
  -H "Accept: application/vnd.heroku+json; version=3" \\
  -H "Content-Type: application/json" \\
  -d "$BODY" \\
  "https://api.heroku.com/apps/$APP/config-vars"
```

To get an API key, run `heroku authorizations:create` or use the Account Settings → Authorizations page. Use scoped tokens (read/write/deploy) instead of global keys."""),
        ("Scale dynos and view logs", """Scale formation:
```bash
BODY=$(jq -n '{updates: [{type: "web", quantity: 3}]}')
curl -s -X PATCH -H "Authorization: Bearer $KEY" -H "Accept: application/vnd.heroku+json; version=3" -H "Content-Type: application/json" -d "$BODY" "https://api.heroku.com/apps/$APP/formation"
```

Tail logs:
```bash
BODY=$(jq -n '{tail: true, lines: 100, source: "app"}')
URL=$(curl -s -X POST -H "Authorization: Bearer $KEY" -H "Accept: application/vnd.heroku+json; version=3" -H "Content-Type: application/json" -d "$BODY" "https://api.heroku.com/apps/$APP/log-sessions" | jq -r '.logplex_url')
curl -s "$URL"
```"""),
        ("Rollback to previous release", """To rollback Heroku app to a previous version:

```bash
BODY=$(jq -n --arg v "v42" '{release: $v}')

curl -s -X POST \\
  -H "Authorization: Bearer $KEY" \\
  -H "Accept: application/vnd.heroku+json; version=3" \\
  -H "Content-Type: application/json" \\
  -d "$BODY" \\
  "https://api.heroku.com/apps/$APP/releases"
```

This is destructive — make sure you've reviewed the diff between v42 and current before rolling back."""),
    ],
    "shopify": [
        ("List products in a Shopify store", """Use Shopify Admin GraphQL API. The current stable version is 2026-04.

```bash
SHOP="your-store.myshopify.com"
TOKEN="$SHOPIFY_ACCESS_TOKEN"  # shpat_*

QUERY='query { products(first: 10) { edges { node { id title handle status totalInventory } } } }'

BODY=$(jq -n --arg q "$QUERY" '{query: $q}')

curl -s -X POST \\
  -H "X-Shopify-Access-Token: $TOKEN" \\
  -H "Content-Type: application/json" \\
  -d "$BODY" \\
  "https://$SHOP/admin/api/2026-04/graphql.json"
```

Get an access token via Shopify admin → Settings → Apps → Develop apps → create Custom App → install."""),
        ("Update product status to ARCHIVED", """For mutations, use productUpdate:

```bash
QUERY='mutation($input: ProductInput!) { productUpdate(input: $input) { product { id status } userErrors { field message } } }'

VARS=$(jq -n --arg id "gid://shopify/Product/123456" '{input: {id: $id, status: "ARCHIVED"}}')

BODY=$(jq -n --arg q "$QUERY" --argjson v "$VARS" '{query: $q, variables: $v}')

curl -s -X POST -H "X-Shopify-Access-Token: $TOKEN" -H "Content-Type: application/json" -d "$BODY" "https://$SHOP/admin/api/2026-04/graphql.json"
```

Check `userErrors` in response — Shopify returns 200 OK but with errors there."""),
        ("Adjust inventory level", """Use inventoryAdjustQuantities:

```bash
QUERY='mutation($input: InventoryAdjustQuantitiesInput!) { inventoryAdjustQuantities(input: $input) { inventoryAdjustmentGroup { id } userErrors { field message } } }'

VARS=$(jq -n --arg item "gid://shopify/InventoryItem/123" --arg loc "gid://shopify/Location/456" --argjson n 5 '{
  input: { reason: "correction", name: "available", changes: [{inventoryItemId: $item, locationId: $loc, delta: $n}] }
}')

BODY=$(jq -n --arg q "$QUERY" --argjson v "$VARS" '{query: $q, variables: $v}')
curl -s -X POST -H "X-Shopify-Access-Token: $TOKEN" -H "Content-Type: application/json" -d "$BODY" "https://$SHOP/admin/api/2026-04/graphql.json"
```

You'll need both `inventoryItemId` and `locationId` (GIDs). Get them via productVariant query first."""),
    ],
    "postgres": [
        ("Find slowest queries", """Use pg_stat_statements (extension must be enabled):

```bash
PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" --set sslmode=require -c "
SELECT
  round(mean_exec_time::numeric, 2) AS avg_ms,
  calls,
  round((total_exec_time / 1000)::numeric, 1) AS total_sec,
  left(query, 100) AS query
FROM pg_stat_statements
ORDER BY mean_exec_time DESC LIMIT 20;"
```

If pg_stat_statements isn't enabled, run `CREATE EXTENSION pg_stat_statements;` (requires superuser).

Use `--set sslmode=require` minimum for non-localhost connections to encrypt traffic."""),
        ("List indexes for a table", """```bash
PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -c "
SELECT
  i.relname AS index,
  pg_size_pretty(pg_relation_size(i.oid)) AS size,
  s.idx_scan AS scans
FROM pg_class i
JOIN pg_index ix ON i.oid = ix.indexrelid
JOIN pg_class t ON t.oid = ix.indrelid
LEFT JOIN pg_stat_user_indexes s ON s.indexrelid = i.oid
WHERE t.relname = 'users';"
```

Indexes with scans=0 after weeks of traffic are removal candidates."""),
    ],
    "k6": [
        ("Generate a basic load test", """Here's a basic k6 script:

```javascript
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  vus: 10,
  duration: '30s',
  thresholds: {
    http_req_duration: ['p(95)<500'],
    http_req_failed: ['rate<0.01'],
  },
};

export default function () {
  const res = http.get('https://staging.example.com/api/health');
  check(res, {
    'status 200': (r) => r.status === 200,
    'duration < 500ms': (r) => r.timings.duration < 500,
  });
  sleep(1);
}
```

Run: `k6 run script.js --summary-export=summary.json`

Don't run against prod without rate limit awareness — k6 with 100 VUs can DDoS your own service."""),
        ("Analyze k6 test results", """Parse the summary JSON:

```bash
jq -r '
  "Requests:    \\(.metrics.http_reqs.values.count)
Failures:    \\(.metrics.http_req_failed.values.rate * 100 | tostring | .[0:5])%
p50:         \\(.metrics.http_req_duration.values[\\"p(50)\\"]) ms
p95:         \\(.metrics.http_req_duration.values[\\"p(95)\\"]) ms
p99:         \\(.metrics.http_req_duration.values[\\"p(99)\\"]) ms
RPS:         \\(.metrics.http_reqs.values.rate | floor)"
' summary.json
```

Watch for: failures > 1%, p95 exceeding SLO, RPS plateau (= bottleneck)."""),
    ],
    "maestro": [
        ("Write a Maestro flow for login", """Maestro uses YAML. Save as `flows/login.yaml`:

```yaml
appId: com.example.app
name: Valid login flow
tags:
  - smoke
  - login
---
- launchApp
- assertVisible: "Welcome"
- tapOn: "Email"
- inputText: "${EMAIL}"
- tapOn: "Password"
- inputText: "${PASSWORD}"
- tapOn: "Sign in"
- assertVisible: "Home"
```

Run: `EMAIL=test@example.com PASSWORD=xxx maestro test flows/login.yaml`

For interactive recording: `maestro record flows/login.yaml` opens an inspector. Tap elements on the device to record actions."""),
        ("Detect flaky Maestro tests", """Run the suite multiple times with JUnit output:

```bash
for i in 1 2 3 4 5; do
  maestro test --format junit --output /tmp/maestro-$i/ flows/
done

# Then aggregate to find flaky ones (passed AND failed across runs)
python3 -c '
import xml.etree.ElementTree as ET, glob
from collections import defaultdict
results = defaultdict(list)
for f in glob.glob("/tmp/maestro-*/*.xml"):
  for tc in ET.parse(f).iter("testcase"):
    failed = tc.find("failure") is not None
    results[tc.get("name")].append(failed)
for name, runs in results.items():
  if any(runs) and not all(runs):
    print(f"{name}: {sum(runs)}/{len(runs)} fail rate")
'
```"""),
    ],
}


def main():
    print("=" * 80)
    print("REALISTIC 'WITHOUT SKILL' BASELINE — measure actual ad-hoc responses")
    print("=" * 80)
    print()
    print(f"{'Skill':<16} {'Tasks':>6} {'Min':>5} {'Max':>5} {'Avg':>5}  {'p50':>5}")
    print("-" * 60)

    grand_total = []

    for skill, tasks in SAMPLES.items():
        token_counts = [tok(response) for _, response in tasks]
        token_counts.sort()
        n = len(token_counts)
        avg = sum(token_counts) // n
        p50 = token_counts[n // 2]
        print(
            f"{skill:<16} "
            f"{n:>6} "
            f"{min(token_counts):>5} "
            f"{max(token_counts):>5} "
            f"{avg:>5} "
            f"{p50:>6}"
        )
        grand_total.extend(token_counts)

    grand_total.sort()
    n = len(grand_total)
    print("-" * 60)
    print(
        f"{'OVERALL':<16} "
        f"{n:>6} "
        f"{min(grand_total):>5} "
        f"{max(grand_total):>5} "
        f"{sum(grand_total)//n:>5} "
        f"{grand_total[n//2]:>6}"
    )
    print()
    print("=" * 80)
    print("COMPARISON vs prior heuristic estimate")
    print("=" * 80)
    print()
    print("Prior heuristic 'without skill' estimate (in benchmark_tokens.py):")
    print("  body * 1.5 + retry overhead")
    print()
    print(f"Realistic measurement (above):")
    print(f"  Mean:   {sum(grand_total)//n} tokens per task")
    print(f"  Median: {grand_total[n//2]} tokens per task")
    print(f"  Range:  {min(grand_total)} - {max(grand_total)} tokens")
    print()
    print("If realistic mean < heuristic mean → toolkit savings are LOWER than")
    print("originally claimed. If realistic mean > heuristic → savings are HIGHER.")
    print()


if __name__ == "__main__":
    main()
