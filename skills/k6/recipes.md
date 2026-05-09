# /k6 — recipes (load on demand)

> Loaded by SKILL.md only when user invokes a specific dispatch verb
> (`gen`, `run`, `analyze`).

## Setup (already loaded in SKILL.md)

```bash
source "$HOME/.claude-team-toolkit/lib/credentials.sh"
ctt_load_creds k6 "${PROFILE:-}"
# now: $CTT_BASE_URL, $CTT_AUTH_HEADER, $CTT_VUS, $CTT_DURATION, $CTT_REQUIRE_CONFIRM
```

## Dispatch

### `gen <type> <endpoint> [--method GET|POST|...]` — generate script

`type` ∈ `smoke | load | stress | soak | spike`.

| Type | Stages |
|---|---|
| smoke | `1 VU, 30s` (sanity check) |
| load | `ramp 0→VUs over 30s, hold VUs for duration, ramp down 30s` |
| stress | `ramp to 2× VUs progressively, find breakpoint` |
| soak | `VUs for 1h+ to detect leaks` |
| spike | `0 → 10× VUs in 10s, hold 1m, drop` |

Write to `tests/k6/<endpoint>-<type>.js`:

```js
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  // populated from template based on type
};

const BASE = __ENV.K6_BASE_URL;
const AUTH = __ENV.K6_AUTH_HEADER;

export default function () {
  const res = http.get(`${BASE}<ENDPOINT>`, {
    headers: AUTH ? { Authorization: AUTH } : {},
  });
  check(res, {
    'status is 200': (r) => r.status === 200,
    'duration < 500ms': (r) => r.timings.duration < 500,
  });
  sleep(1);
}
```

NEVER bake credentials into the script — always read from env. The skill
sets `K6_BASE_URL` and `K6_AUTH_HEADER` from the profile when running.

### `run <script> [--profile <name>]` — execute test

```bash
ctt_load_creds k6 "$PROFILE"

# Safety: require explicit confirmation for prod-like profiles
if [ "$CTT_REQUIRE_CONFIRM" = "true" ]; then
  source "$HOME/.claude-team-toolkit/lib/confirm.sh"
  ctt_confirm "Run k6 against $CTT_BASE_URL ($CTT_PROFILE) with $CTT_VUS VUs for $CTT_DURATION?" "RUN" || return 1
fi

K6_BASE_URL="$CTT_BASE_URL" \
K6_AUTH_HEADER="$CTT_AUTH_HEADER" \
  k6 run \
    --vus "$CTT_VUS" \
    --duration "$CTT_DURATION" \
    --summary-export=/tmp/k6-summary.json \
    "$SCRIPT"

ctt_audit_log k6 "ran $SCRIPT against $CTT_PROFILE"
```

### `analyze <summary.json>` — interpret last run

```bash
jq -r '
  "Requests:    \(.metrics.http_reqs.values.count)
Failures:    \(.metrics.http_req_failed.values.rate * 100 | tostring | .[0:5])%
p50:         \(.metrics.http_req_duration.values["p(50)"]) ms
p95:         \(.metrics.http_req_duration.values["p(95)"]) ms
p99:         \(.metrics.http_req_duration.values["p(99)"]) ms
RPS:         \(.metrics.http_reqs.values.rate | floor)
VUs (max):   \(.metrics.vus_max.values.max)
Data sent:   \(.metrics.data_sent.values.count) bytes
Data recv:   \(.metrics.data_received.values.count) bytes"
' "$SUMMARY"
```

Highlight RED flags:
- `http_req_failed > 1%` → reliability issue
- `p95 > target SLO` → perf regression
- Trend across runs (if `tests/k6/baseline.json` exists, compare)

## Implementation notes

- k6 requires JS files (not TS). Use `import` syntax, not `require`.
- `__ENV.X` is k6's way to read env vars inside the script.
- For browser tests use `k6/browser` (separate dependency, heavier).
- `--quiet` suppresses progress bar; useful in CI but lose live feedback.
- Output formats: `--summary-export=json` for parsing, `--out json=file.gz` for full timeseries.
