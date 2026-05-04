---
name: k6
description: k6 load/stress/soak/spike tests. Multi-environment profiles (dev/staging/prod base URLs + auth). Generate scripts (smoke/load/stress/soak/spike), run, analyze p50/p95/p99. Prod profile requires typed RUN confirmation. VU cap protects against accidental DDoS.
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Bash
---

# /k6 — load testing with environment profiles

Wrapper around [k6](https://k6.io/) for load/stress/soak tests. Profiles
select target environment (dev/staging/prod) so the same script runs against
different hosts with different auth.

Arguments: `$ARGUMENTS`. Profile resolution: `--profile <name>` flag → `K6_PROFILE` env → `~/.k6/active_profile` → `[default]`.

## Dependencies

```bash
# Windows
choco install k6                # or: scoop install k6
# macOS
brew install k6
# Linux
sudo gpg -k && sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
sudo apt update && sudo apt install k6
```

Verify: `k6 version`. If missing, stop.

## Profile config

`~/.k6/credentials` (mode 600 — may contain auth tokens):

```ini
[default]
base_url = http://localhost:3000
auth_header =
vus = 10
duration = 30s

[staging]
base_url = https://staging.example.com
auth_header = Bearer eyJxxxxxxxx...
vus = 50
duration = 2m

[prod]
base_url = https://api.example.com
auth_header = Bearer eyJxxxxxxxx...
vus = 100
duration = 5m
# prod is special — require explicit confirmation before running
require_confirm = true
```

Load via shared helper:

```bash
source "$HOME/.claude-team-toolkit/lib/credentials.sh"
ctt_load_creds k6 "${PROFILE:-}"
# now: $CTT_BASE_URL, $CTT_AUTH_HEADER, $CTT_VUS, $CTT_DURATION, $CTT_REQUIRE_CONFIRM
```

## Dispatch

### `gen <type> <endpoint> [--method GET|POST|...]` — generate script

`type` ∈ `smoke | load | stress | soak | spike`.

Templates differ in stage shape:

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

### `profile add|list|use|remove` — manage targets

Same pattern as Trello/Azure DevOps profiles. See `lib/credentials.sh`.

## Safety

- **Never run prod profile without explicit user confirmation.** The
  `require_confirm = true` field forces the typed `RUN` confirmation.
- **VU caps:** the skill should refuse `--vus > 1000` without an extra
  `--force` flag — typo-protection against accidentally DDoSing your own
  service.
- **No credential interpolation** into the JS script. Pass auth via env var
  only. Scripts may be committed to git — credentials must not be.
- **Rate limit awareness:** if testing a 3rd-party API (not your own
  service), add `--rps` cap. Default `--rps 0` = unlimited = will get IP
  banned from real APIs.
- Output `summary-export` JSON may contain URLs, response samples — treat as
  potentially sensitive (PII in error messages, etc.). Don't paste public.

## Implementation notes

- k6 requires JS files (not TS). Use `import` syntax, not `require`.
- `__ENV.X` is k6's way to read env vars inside the script.
- For browser tests use `k6/browser` (separate dependency, heavier).
- `--quiet` suppresses progress bar; useful in CI but lose live feedback.
- Output formats: `--summary-export=json` for parsing, `--out json=file.gz`
  for full timeseries.
