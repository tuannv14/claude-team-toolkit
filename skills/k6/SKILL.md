---
name: k6
description: Use when running load, stress, soak, or spike tests, or analyzing p50/p95/p99 latency against dev/staging/prod targets. Multi-environment via K6_PROFILE; prod requires typed RUN confirmation.
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Bash
---

# /k6 — load testing with environment profiles

Wrapper around [k6](https://k6.io/) for load/stress/soak tests. Profiles
select target environment (dev/staging/prod) so the same script runs against
different hosts with different auth. Profile resolution: `--profile <name>`
→ `K6_PROFILE` → `~/.k6/active_profile` → `[default]`.

## Overview

Profiles select the target environment so the same script runs against
different hosts with different auth. Prod profiles require typed `RUN`
confirmation to prevent accidental DDoS of own infrastructure.

## When to Use

- Pre-release load testing (smoke/load before deploy)
- Capacity planning (find breakpoint with stress test)
- Soak tests (memory leaks, connection pool issues over time)
- Latency regression tracking (p50/p95/p99 vs baseline)
- Spike tests (cold cache, autoscaling validation)

## When NOT to Use

- Hitting third-party APIs without their consent → DDoS / TOS violation
- Functional testing → k6 is for load, not assertion-heavy logic
- Browser-based UI testing → use Maestro/Detox, not k6
- VUs > 1000 without `--force` → almost always a typo

## Dependencies

```bash
choco install k6        # Windows (or scoop install k6)
brew install k6         # macOS
# Linux: see https://k6.io/docs/get-started/installation/
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
require_confirm = true                   # prod special: require typed RUN
```

> Shared profile/INI/`ctt_*` pattern reference: [profiles-and-credentials](../profiles-and-credentials/SKILL.md).

## Dispatch verbs

| Verb | Purpose |
|---|---|
| `gen <type> <endpoint>` | Generate `tests/k6/<endpoint>-<type>.js` from template |
| `run <script>` | Execute against profile target; prod requires typed RUN |
| `analyze <summary.json>` | Print p50/p95/p99/RPS summary |
| `profile add\|list\|use\|remove` | Manage targets (shared CTT pattern) |

## Reference files (load on demand)

- **[recipes.md](recipes.md)** — full templates per type (smoke/load/stress/soak/spike), `run` flow with confirmation gate, `analyze` jq query. Load when user invokes `gen`, `run`, or `analyze`.

## Common Mistakes

- Hard-coding auth in JS script → leaks on commit. Use env vars (`__ENV.X`).
- No `--rps` cap when testing 3rd-party APIs → IP gets banned
- Wrong test type for the question: stress to find breakpoint, soak for leaks, load for SLO
- Comparing runs across environments → pointless. Compare same env over time.
- Running prod profile without `require_confirm=true` set
- VUs > 1000 without `--force` flag → almost always a typo

## Safety

- **Never run prod profile without explicit user confirmation.** The `require_confirm = true` field forces the typed `RUN` confirmation.
- **VU caps:** the skill should refuse `--vus > 1000` without an extra `--force` flag — typo-protection against accidentally DDoSing your own service.
- **No credential interpolation** into the JS script. Pass auth via env var only. Scripts may be committed to git — credentials must not be.
- **Rate limit awareness:** if testing a 3rd-party API, add `--rps` cap. Default `--rps 0` = unlimited = will get IP banned from real APIs.
- Output `summary-export` JSON may contain URLs and response samples — treat as potentially sensitive; don't paste publicly.
