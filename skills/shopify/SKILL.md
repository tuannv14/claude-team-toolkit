---
name: shopify
description: Shopify Admin GraphQL API for products/orders/customers/inventory. Use for product/order queries, inventory updates, draft orders. Multi-store + multi-app via SHOPIFY_PROFILE. API 2026-04 default.
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Bash
---

# /shopify — Admin GraphQL API (multi-store, multi-app)

REST/GraphQL against `https://<shop>.myshopify.com/admin/api/<version>/`.
GraphQL primary (Shopify's recommended). Each profile = one
`(shop_domain, access_token)` pair → supports multi-store AND multi-app
on same store.

Profile resolution: `--profile` → `SHOPIFY_PROFILE` → `~/.shopify/active_profile` → `[default]`.

## Profile config

`~/.shopify/credentials` (mode 600):

```ini
[default]
shop_domain  = your-store.myshopify.com
access_token = shpat_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
api_version  = 2026-04                 # bump quarterly

[main-inventory]
shop_domain  = your-store.myshopify.com   # same store, different app
access_token = shpat_inventory-app-token  # scopes: read/write_inventory only
api_version  = 2026-04
require_confirm = true
```

**Multi-app benefits:** least-privilege scopes per app, audit separation,
revocation granularity, team boundaries. See
[examples/shopify-credentials.example](../../examples/shopify-credentials.example).

**Get token:** Shopify admin → Settings → Apps → Develop apps → create
Custom App → configure scopes → install → copy `shpat_*` (shown ONCE).

**Required scopes per op (least privilege):**

| Op | Scopes |
|---|---|
| Products read/write | `read_products` (+ `write_products`) |
| Orders read/write | `read_orders` (+ `write_orders`) |
| Customers | `read_customers` (+ `write_customers`) |
| Inventory | `read_inventory` (+ `write_inventory`) |
| Draft orders | `read_draft_orders` + `write_draft_orders` |

**Versioning:** Shopify ships YYYY-MM stable releases quarterly,
supported 12 months. Bump `api_version` quarterly. Never use `unstable`.

## Helpers

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

## Rate limits

- GraphQL: cost-based, 50 pts/sec restore, 1000 max bucket. Check
  `extensions.cost` in response.
- 429 → respect `Retry-After` header.
- Bulk reads → use `bulkOperationRunQuery`.

## Dispatch

### `configure` — interactive setup
Profile name → shop_domain → access_token (hidden) → api_version → require_confirm. Validate via `shop` query. Save mode 600.

### `profile list|use|current|remove` — see lib/credentials.sh

### `shop` — current shop info
```bash
shopify_gql 'query { shop { name email myshopifyDomain currencyCode plan { displayName } } }' | jq '.data.shop'
```

### `products [--limit N] [--query "title:foo"]`
```bash
LIMIT="${LIMIT:-10}"; case "$LIMIT" in ''|*[!0-9]*) LIMIT=10 ;; esac
shopify_gql '
query($f:Int!, $q:String) {
  products(first:$f, query:$q) {
    edges { node { id title handle status totalInventory priceRangeV2 { minVariantPrice { amount currencyCode } } } }
  }
}' "$(jq -n --argjson f "$LIMIT" --arg q "$QUERY" '{f:$f, q:$q}')"
```

### `product <gid>` — full product (id = `gid://shopify/Product/<num>`)
```bash
shopify_gql '
query($id:ID!) {
  product(id:$id) {
    id title vendor productType status tags descriptionHtml
    priceRangeV2 { minVariantPrice { amount } maxVariantPrice { amount } }
    variants(first:50) { edges { node { id title sku price inventoryQuantity } } }
  }
}' "$(jq -n --arg id "$ID" '{id:$id}')"
```

### `orders [--status open|closed|any] [--limit N]`
```bash
shopify_gql '
query($f:Int!, $q:String) {
  orders(first:$f, query:$q, sortKey:CREATED_AT, reverse:true) {
    edges { node {
      id name email createdAt
      totalPriceSet { shopMoney { amount currencyCode } }
      displayFinancialStatus displayFulfillmentStatus
      customer { displayName email }
    } }
  }
}' "$(jq -n --argjson f "$LIMIT" --arg q "${STATUS:+status:$STATUS}" '{f:$f, q:$q}')"
```

### `order <gid>` — full order with line items + fulfillments
```bash
shopify_gql '
query($id:ID!) {
  order(id:$id) {
    id name email phone createdAt cancelledAt
    totalPriceSet { shopMoney { amount currencyCode } }
    displayFinancialStatus displayFulfillmentStatus
    shippingAddress { name address1 city province country zip }
    lineItems(first:50) { edges { node { title quantity sku } } }
    fulfillments { id status trackingInfo { number url } }
  }
}' "$(jq -n --arg id "$ID" '{id:$id}')"
```

### `customers [--query] [--limit N]`
```bash
shopify_gql '
query($f:Int!, $q:String) {
  customers(first:$f, query:$q) {
    edges { node { id displayName email phone numberOfOrders amountSpent { amount } } }
  }
}' "$(jq -n --argjson f "$LIMIT" --arg q "$QUERY" '{f:$f, q:$q}')"
```

### `inventory <variant-gid>` — current levels per location
```bash
shopify_gql '
query($id:ID!) {
  productVariant(id:$id) {
    id sku title
    inventoryItem { tracked inventoryLevels(first:10) { edges { node { available location { name } } } } }
  }
}' "$(jq -n --arg id "$VARIANT_ID" '{id:$id}')"
```

### `update-product <gid> <field=value>...` — DESTRUCTIVE
Fields: `title`, `status` (`ACTIVE|DRAFT|ARCHIVED`), `tags`, `vendor`, `productType`.
```bash
ctt_warn_destructive "Update product $ID on $CTT_SHOP_DOMAIN ($CTT_PROFILE)"
ctt_confirm "Type product ID to confirm:" "$ID" || return 1

INPUT=$(jq -n '{id:$id} + ($args | map(split("=")) | map({key:.[0], value:.[1]}) | from_entries)' \
  --arg id "$ID" --slurpfile args <(printf '%s\n' "$@" | jq -R .))

shopify_gql '
mutation($input:ProductInput!) {
  productUpdate(input:$input) { product { id title status } userErrors { field message } }
}' "$(jq -n --argjson i "$INPUT" '{input:$i}')"

ctt_audit_log shopify "update-product $ID fields: $(echo "$@" | sed 's/=[^ ]*//g')"
```

### `update-inventory <variant-gid> <count> [--location <gid>]` — DESTRUCTIVE
```bash
ctt_warn_destructive "Set inventory $VARIANT_ID = $COUNT"
ctt_confirm "Type variant ID:" "$VARIANT_ID" || return 1

ITEM=$(shopify_gql "{ productVariant(id:\"$VARIANT_ID\"){ inventoryItem { id } } }" | jq -r '.data.productVariant.inventoryItem.id')
LOC="${LOCATION:-$(shopify_gql '{ locations(first:1){ edges{ node{ id } } } }' | jq -r '.data.locations.edges[0].node.id')}"

shopify_gql '
mutation($input:InventoryAdjustQuantitiesInput!) {
  inventoryAdjustQuantities(input:$input) {
    inventoryAdjustmentGroup { id } userErrors { field message }
  }
}' "$(jq -n --arg item "$ITEM" --arg loc "$LOC" --argjson n "$COUNT" '{
  input: { reason:"correction", name:"available", changes:[{inventoryItemId:$item, locationId:$loc, delta:$n}] }
}')"

ctt_audit_log shopify "inventory-set variant=$VARIANT_ID count=$COUNT"
```

### `gql <query-file-or-string> [variables-json]` — raw GraphQL escape hatch
For draft orders, bulk operations, webhooks, custom field selections.
```bash
QUERY=$([ -f "$1" ] && cat "$1" || echo "$1")
shopify_gql "$QUERY" "${2:-{}}"
```

Example bulk read:
```bash
/shopify gql 'mutation { bulkOperationRunQuery(query:"...") { bulkOperation { id status } } }'
/shopify gql '{ currentBulkOperation { id status objectCount url } }'   # poll
```

## Safety

- `access_token` = full granted scopes for that store. **Never log raw**.
  Skill masks as `****<last4>`.
- All mutations gated by `ctt_confirm`. Set `require_confirm=true` on prod.
- `update-product` requires typing product ID to confirm.
- **Not in skill** (intentionally): product/customer delete, order cancel
  → use Shopify admin UI for those.
- Rate limits surfaced as errors, not auto-retried — caller decides.
- PII in customers/orders → don't paste raw output publicly.
- Compromise: revoke at admin → Settings → Apps → Uninstall.
