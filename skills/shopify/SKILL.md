---
name: shopify
description: "Use when user references Shopify, *.myshopify.com URLs, admin.shopify.com links, or asks to query/mutate products/orders/customers/inventory/draft-orders via Admin GraphQL. Multi-store and multi-app via SHOPIFY_PROFILE."
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Bash
---

# /shopify — Admin GraphQL API (multi-store, multi-app)

GraphQL against `https://<shop>.myshopify.com/admin/api/<version>/`.
Each profile = one `(shop_domain, access_token)` pair → multi-store AND
multi-app on the same store (least-privilege scopes per app).

Profile resolution: `--profile` → `SHOPIFY_PROFILE` → `~/.shopify/active_profile` → `[default]`.

## Overview

GraphQL primary against the Admin API. Each profile = one `(shop_domain, access_token)` pair, supporting multi-store AND multi-app on the same store (least-privilege scopes per app — e.g., separate inventory app vs read-only reporting app).

## When to Use

- Querying products / orders / customers / inventory programmatically
- Bulk read via `bulkOperationRunQuery` for large catalogs
- Inventory adjustments across multiple locations
- Draft order creation for B2B / wholesale flows
- Multi-store support (parent brand + child stores)

## When NOT to Use

- Storefront API (customer-facing) → different API, different auth
- Theme development → use Shopify CLI's theme commands
- App development → use Shopify CLI's app commands + framework
- One-off Liquid changes → admin UI is faster

## Profile config

`~/.shopify/credentials` (mode 600):

```ini
[default]
shop_domain  = your-store.myshopify.com
access_token = shpat_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
api_version  = 2026-04                 # bump quarterly
require_confirm = true                 # gate mutations on prod
```

See [examples/shopify-credentials.example](../../examples/shopify-credentials.example) for multi-app setup.

**Get token:** Shopify admin → Settings → Apps → Develop apps → create
Custom App → configure scopes → install → copy `shpat_*` (shown ONCE).

**Required scopes** (least privilege): `read_products`, `read_orders`,
`read_customers`, `read_inventory`, `read_draft_orders`. Add the `write_*`
counterpart only for mutating ops.

**Versioning:** Shopify ships YYYY-MM stable releases quarterly, supported
12 months. Bump `api_version` quarterly. Never use `unstable`.

## Helpers

> Shared profile/INI/`ctt_*` pattern reference: [profiles-and-credentials](../profiles-and-credentials/SKILL.md).

```bash
source "$HOME/.claude-team-toolkit/lib/credentials.sh"
source "$HOME/.claude-team-toolkit/lib/confirm.sh"
ctt_load_creds shopify "$PROFILE"

case "$CTT_SHOP_DOMAIN" in
  *.myshopify.com) ;;
  *) echo "Invalid shop_domain (must end .myshopify.com)" >&2; return 1 ;;
esac
BASE="https://$CTT_SHOP_DOMAIN/admin/api/${CTT_API_VERSION:-2026-04}"

shopify_gql() {
  local body
  body=$(jq -n --arg q "$1" --argjson v "${2:-{}}" '{query:$q, variables:$v}')
  curl -s --ssl-no-revoke -X POST \
    -H "X-Shopify-Access-Token: $CTT_ACCESS_TOKEN" \
    -H "Content-Type: application/json" \
    -d "$body" "$BASE/graphql.json"
}
```

## Commands

| Subcommand | Purpose |
|---|---|
| `configure` | Interactive profile setup |
| `profile {list,use,current,remove}` | Profile management |
| `shop` | Current shop info |
| `products [--limit N] [--query]` | List products |
| `product <gid>` | Full product detail |
| `orders [--status] [--limit N]` | Recent orders |
| `order <gid>` | Full order + line items + fulfillments |
| `customers [--query] [--limit N]` | List customers |
| `inventory <variant-gid>` | Levels per location |
| `update-product <gid> <field=value>...` | **DESTRUCTIVE** |
| `update-inventory <variant-gid> <count>` | **DESTRUCTIVE** |
| `gql <query-or-file> [vars]` | Raw GraphQL escape hatch |

Full query and mutation bodies: see [commands.md](commands.md).

## Rate limits

GraphQL cost-based: 50 pts/sec restore, 1000 max bucket. Check
`extensions.cost` in the response. On `429` respect `Retry-After`.
For bulk reads use `bulkOperationRunQuery`.

## Common Mistakes

- Using `unstable` API version → breaks weekly. Pin to YYYY-MM stable.
- Storing token in code/git → revoke immediately, rotate
- Querying without rate awareness → 429 storms. Check `extensions.cost`.
- Bulk read with offset pagination instead of `bulkOperationRunQuery` → slow + rate-limited
- One mega-app with all scopes → can't audit which feature uses what. Split per concern.
- Forgetting `gid://shopify/<Type>/<id>` format on mutations → user errors

## Safety

- `access_token` grants the full scope set for that store. **Never log
  raw** — skill masks as `****<last4>`.
- All mutations gated by `ctt_confirm`. Set `require_confirm=true` on prod.
- `update-product` requires typing the product ID to confirm.
- **Excluded intentionally:** product/customer delete, order cancel → use
  admin UI.
- Rate-limit errors are surfaced, not auto-retried — caller decides.
- PII in customers/orders → don't paste raw output publicly.
- On token compromise: revoke at Settings → Apps → Uninstall.
