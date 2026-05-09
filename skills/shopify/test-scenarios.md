# /shopify test scenarios

Application + retrieval scenarios for verifying the shopify skill (a Reference type skill — testing focuses on whether agents find and apply the right pattern, not on enforcing discipline). Per [superpowers:writing-skills](#) Iron Law: every edit to this skill SHOULD re-run these against a subagent before/after.

## How to run

Dispatch a subagent (general-purpose) with each scenario prompt. Compare:
- **Baseline (RED):** WITHOUT skill loaded — does agent guess correctly?
- **With skill (GREEN):** WITH SKILL.md + commands.md loaded — does agent find and apply the correct pattern?

## Scenario 1 — Multi-store query (retrieval test)

**Prompt:**
> User has two Shopify stores: a parent brand and a wholesale child store. They want to list the 10 most recent orders from BOTH stores. They mention "we use the shopify skill". Show them how.

**Expected GREEN behavior:**
- Identifies that `SHOPIFY_PROFILE` env var or `--profile` flag selects store
- Runs `/shopify orders --limit 10 --profile parent` then `--profile wholesale`
- Doesn't try to query both in one call (correct: each profile = one shop_domain)
- Token-saving: doesn't emit full order JSON; uses summary form

## Scenario 2 — Inventory adjustment (mutation pattern)

**Prompt:**
> User wants to set inventory of variant `gid://shopify/ProductVariant/12345` to 50 units at the LA warehouse. Show the safe way.

**Expected GREEN behavior:**
- Uses `update-inventory` subcommand (not raw `gql`)
- Recognizes that the variant gid format is required (not bare ID)
- Triggers `ctt_warn_destructive` + typed variant ID confirmation
- Notes that you need the location gid for the LA warehouse — fetches it first

**Failure modes:**
- Agent uses raw GraphQL escape hatch when a dedicated subcommand exists
- Agent forgets the gid:// prefix → mutation userErrors

## Scenario 3 — Bulk read for analytics (rate-limit awareness)

**Prompt:**
> User wants to export ALL products (about 50,000 of them) to a CSV. Just paginate through `products` and dump them.

**Expected GREEN behavior:**
- Recognizes 50K is too many for offset pagination → 429 storms
- Suggests `bulkOperationRunQuery` via the `gql` escape hatch
- Mentions polling `currentBulkOperation` for completion
- References that result is a JSONL URL, not inline data

**Failure modes:**
- Agent writes a `for page in range(...)` loop with 50K iterations
- Agent doesn't recognize the rate-limit implications
- Agent treats `extensions.cost` as ignorable

## Scenario 4 — API version drift (best practice)

**Prompt:**
> User asks: "Should I use API version `unstable` to get the newest features?"

**Expected GREEN behavior:**
- Refuses `unstable` (breaks weekly per skill's Common Mistakes)
- Recommends pinning to YYYY-MM stable (e.g., 2026-04)
- Notes 12-month support window per Shopify

## Scenario 5 — Token leak hypothetical

**Prompt:**
> User pasted their full `shpat_*` token in chat by accident. What now?

**Expected GREEN behavior:**
- Direct user to revoke at admin → Settings → Apps → Uninstall
- Rotate before re-installing
- Don't echo or repeat the token in response
- Reference safety section pattern

## Coverage matrix

| Skill feature | Scenario testing it |
|---|---|
| Multi-store profiles | 1 |
| Mutation safety (`ctt_confirm`) | 2 |
| Rate limits / bulk | 3 |
| API version policy | 4 |
| Token security | 5 |
| Read-only commands (products, orders, etc.) | 1 |
| Common mistakes section | 3, 4 |

## Test status

| Date | Scenario | Result | Notes |
|------|----------|--------|-------|
| pending | All 5 | not run | First TDD run not yet executed |
