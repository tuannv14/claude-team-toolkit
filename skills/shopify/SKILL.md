---
name: shopify
description: Shopify Admin GraphQL API for products/orders/customers/inventory/draft-orders, multi-store. Use to query/update products, fetch orders, manage inventory, search customers, run raw GraphQL. Latest stable API version 2026-04 (quarterly). Switch stores via --profile or SHOPIFY_PROFILE.
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Bash
---

# /shopify — Shopify Admin GraphQL API (multi-store)

Direct REST/GraphQL against `https://<shop>.myshopify.com/admin/api/<version>/`.
**GraphQL primary** (Shopify's recommended API for new integrations); REST
used only for endpoints not yet on GraphQL.

Arguments: `$ARGUMENTS`. Profile resolution: `--profile` → `SHOPIFY_PROFILE`
→ `~/.shopify/active_profile` → `[default]`.

## Profile config

`~/.shopify/credentials` (mode 600):

```ini
[default]
shop_domain  = your-store.myshopify.com
access_token = shpat_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
api_version  = 2026-04                 # latest stable; bump quarterly

[client_a]
shop_domain  = client-a.myshopify.com
access_token = shpat_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
api_version  = 2026-04
require_confirm = true                 # prod store — gate every mutation
```

**Get an access token (Custom App):**

1. Shopify admin → Settings → Apps and sales channels → Develop apps
2. Create a custom app → Configure Admin API scopes (least privilege below)
3. Install app → reveal Admin API access token (starts with `shpat_`)
4. Token is shown ONCE at install time — copy immediately

**Required scopes by operation** (configure only what you need):

| Operation | Admin API scope |
|---|---|
| List/read products | `read_products` |
| Update products | `read_products` + `write_products` |
| List/read orders | `read_orders` |
| Update orders | `read_orders` + `write_orders` |
| Customers | `read_customers` (+ `write_customers` for updates) |
| Inventory levels | `read_inventory` (+ `write_inventory`) |
| Draft orders | `read_draft_orders` + `write_draft_orders` |

**Versioning:** Shopify ships a new stable version every quarter
(YYYY-MM). Each is supported for **12 months**. Bump `api_version` in your
profile every quarter to stay current. Never use `unstable` in production.

## Helpers

```bash
source "$HOME/.claude-team-toolkit/lib/credentials.sh"
source "$HOME/.claude-team-toolkit/lib/confirm.sh"
ctt_load_creds shopify "$PROFILE"

# Validate shop_domain shape (lowercase, digits, hyphens, ends in .myshopify.com)
case "$CTT_SHOP_DOMAIN" in
  *.myshopify.com) ;;
  *) echo "Invalid shop_domain: $CTT_SHOP_DOMAIN (must end .myshopify.com)" >&2; return 1 ;;
esac

API_VER="${CTT_API_VERSION:-2026-04}"
BASE="https://$CTT_SHOP_DOMAIN/admin/api/$API_VER"

# GraphQL wrapper (preferred)
shopify_gql() {
  local query="$1"
  local variables="${2:-{}}"
  local body
  body=$(jq -n --arg q "$query" --argjson v "$variables" '{query:$q, variables:$v}')
  curl -s --ssl-no-revoke \
    -X POST \
    -H "X-Shopify-Access-Token: $CTT_ACCESS_TOKEN" \
    -H "Content-Type: application/json" \
    -d "$body" \
    "$BASE/graphql.json"
}

# REST wrapper (simple GETs and legacy endpoints)
shopify_rest() {
  local method="$1" path="$2"; shift 2
  curl -s --ssl-no-revoke -X "$method" \
    -H "X-Shopify-Access-Token: $CTT_ACCESS_TOKEN" \
    -H "Content-Type: application/json" \
    -H "Accept: application/json" \
    "$@" \
    "$BASE$path"
}
```

## Rate limits

- **GraphQL**: cost-based, 50 points/sec restore, 1000 max bucket. Heavy
  queries return `extensions.cost` — respect it.
- **REST**: 2 req/sec leaky bucket per app per shop (Plus: 4 req/sec).
- 429 responses include `Retry-After` header.
- For bulk reads, use **Bulk Operations** (GraphQL `bulkOperationRunQuery`).

## Dispatch

### `configure` — interactive setup
Prompt: profile name → shop_domain → access_token (hidden) → api_version
(default 2026-04) → require_confirm. Validate by querying `shop` GraphQL
field. Save to creds file (mode 600). Show shop name + masked token.

### `profile list|use|current|remove` — see lib/credentials.sh

### `shop` — current shop info

```bash
shopify_gql 'query { shop { name email myshopifyDomain primaryDomain { url } currencyCode plan { displayName } } }' \
  | jq '.data.shop'
```

### `products [--limit N] [--query "title:foo"]`

```bash
QUERY="${QUERY:-}"
LIMIT="${LIMIT:-10}"
case "$LIMIT" in ''|*[!0-9]*) LIMIT=10 ;; esac

shopify_gql "
query(\$first: Int!, \$query: String) {
  products(first: \$first, query: \$query) {
    edges {
      node {
        id title handle status
        priceRangeV2 { minVariantPrice { amount currencyCode } }
        totalInventory
        onlineStoreUrl
      }
    }
    pageInfo { hasNextPage endCursor }
  }
}" "$(jq -n --argjson f "$LIMIT" --arg q "$QUERY" '{first:$f, query:$q}')" \
  | jq -r '.data.products.edges[] | "\(.node.id)\t\(.node.title)\t\(.node.status)\t\(.node.totalInventory) units"'
```

### `product <id>` — full product detail (id = `gid://shopify/Product/<num>`)

```bash
shopify_gql "
query(\$id: ID!) {
  product(id: \$id) {
    id title handle vendor productType status tags
    descriptionHtml
    priceRangeV2 { minVariantPrice { amount } maxVariantPrice { amount } }
    totalInventory
    variants(first: 50) {
      edges { node { id title sku price inventoryQuantity } }
    }
    images(first: 10) { edges { node { url altText } } }
  }
}" "$(jq -n --arg id "$ID" '{id:$id}')"
```

### `orders [--status open|closed|any] [--limit N]`

```bash
STATUS_FILTER=""
case "$STATUS" in
  open) STATUS_FILTER="status:open" ;;
  closed) STATUS_FILTER="status:closed" ;;
  *) STATUS_FILTER="" ;;
esac

shopify_gql "
query(\$first: Int!, \$query: String) {
  orders(first: \$first, query: \$query, sortKey: CREATED_AT, reverse: true) {
    edges {
      node {
        id name email
        createdAt processedAt
        totalPriceSet { shopMoney { amount currencyCode } }
        displayFinancialStatus displayFulfillmentStatus
        customer { displayName email }
      }
    }
  }
}" "$(jq -n --argjson f "$LIMIT" --arg q "$STATUS_FILTER" '{first:$f, query:$q}')"
```

### `order <id>` — full order detail

```bash
shopify_gql "
query(\$id: ID!) {
  order(id: \$id) {
    id name email phone
    createdAt processedAt cancelledAt
    totalPriceSet { shopMoney { amount currencyCode } }
    subtotalPriceSet { shopMoney { amount } }
    totalShippingPriceSet { shopMoney { amount } }
    totalTaxSet { shopMoney { amount } }
    displayFinancialStatus displayFulfillmentStatus
    customer { id displayName email }
    shippingAddress { name address1 city province country zip }
    lineItems(first: 50) {
      edges { node { title quantity sku variant { price } } }
    }
    fulfillments { id status trackingInfo { number url } }
  }
}" "$(jq -n --arg id "$ID" '{id:$id}')"
```

### `customers [--query] [--limit N]`

```bash
shopify_gql "
query(\$first: Int!, \$query: String) {
  customers(first: \$first, query: \$query) {
    edges {
      node {
        id displayName email phone
        numberOfOrders
        amountSpent { amount currencyCode }
        createdAt
      }
    }
  }
}" "$(jq -n --argjson f "$LIMIT" --arg q "$QUERY" '{first:$f, query:$q}')"
```

### `inventory <variant-id>` — current inventory levels

```bash
shopify_gql "
query(\$id: ID!) {
  productVariant(id: \$id) {
    id sku title
    inventoryItem {
      id tracked
      inventoryLevels(first: 10) {
        edges { node { available location { name } } }
      }
    }
  }
}" "$(jq -n --arg id "$VARIANT_ID" '{id:$id}')"
```

### `update-product <id> <field=value>...` — DESTRUCTIVE

Common fields: `title`, `status` (`ACTIVE|DRAFT|ARCHIVED`), `tags`, `vendor`,
`productType`. For variant pricing use `update-variant`.

```bash
ctt_warn_destructive "Update product $ID on $CTT_SHOP_DOMAIN ($CTT_PROFILE)"
[ "$CTT_REQUIRE_CONFIRM" = "true" ] && ctt_confirm "Update product? Type the product ID to confirm:" "$ID" || \
  ctt_confirm "Update product on $CTT_PROFILE?" || return 1

# Build JSON input from key=value args
INPUT_JSON=$(jq -n '{id:$id} + ($args | map(split("=")) | map({key:.[0], value:.[1]}) | from_entries)' \
  --arg id "$ID" --slurpfile args <(printf '%s\n' "$@" | jq -R .))

shopify_gql '
mutation($input: ProductInput!) {
  productUpdate(input: $input) {
    product { id title status }
    userErrors { field message }
  }
}' "$(jq -n --argjson input "$INPUT_JSON" '{input:$input}')"

ctt_audit_log shopify "update-product $ID fields: $(echo "$@" | sed 's/=[^ ]*//g')"
```

Audit log records field NAMES only, not values.

### `update-inventory <variant-id> <count> [--location <id>]` — DESTRUCTIVE

```bash
ctt_warn_destructive "Set inventory $VARIANT_ID = $COUNT on $CTT_SHOP_DOMAIN"
ctt_confirm "Set inventory? Type the variant ID:" "$VARIANT_ID" || return 1

# Get inventoryItemId from variant
ITEM_ID=$(shopify_gql "{ productVariant(id:\"$VARIANT_ID\"){ inventoryItem { id } } }" \
  | jq -r '.data.productVariant.inventoryItem.id')

LOC_ID="${LOCATION:-$(shopify_gql '{ locations(first:1){ edges{ node{ id } } } }' | jq -r '.data.locations.edges[0].node.id')}"

shopify_gql '
mutation($input: InventoryAdjustQuantitiesInput!) {
  inventoryAdjustQuantities(input: $input) {
    inventoryAdjustmentGroup { id }
    userErrors { field message }
  }
}' "$(jq -n --arg item "$ITEM_ID" --arg loc "$LOC_ID" --argjson n "$COUNT" '{
  input: {
    reason: "correction",
    name: "available",
    changes: [{inventoryItemId:$item, locationId:$loc, delta:$n}]
  }
}')"

ctt_audit_log shopify "inventory-set variant=$VARIANT_ID count=$COUNT"
```

### `draft-order create <line-items-json>` — create draft order

```bash
shopify_gql '
mutation($input: DraftOrderInput!) {
  draftOrderCreate(input: $input) {
    draftOrder { id name invoiceUrl totalPriceSet { shopMoney { amount currencyCode } } }
    userErrors { field message }
  }
}' "$(jq -n --argjson items "$LINE_ITEMS" '{input: {lineItems: $items}}')"
```

### `webhooks` — list configured webhooks

```bash
shopify_gql '{
  webhookSubscriptions(first: 50) {
    edges { node { id topic callbackUrl format } }
  }
}'
```

### `gql <query-file-or-string>` — raw GraphQL escape hatch

```bash
QUERY=$([ -f "$1" ] && cat "$1" || echo "$1")
VARS="${2:-{}}"
shopify_gql "$QUERY" "$VARS"
```

Useful for:
- Bulk operations (`bulkOperationRunQuery`)
- New endpoints not yet wrapped in this skill
- Custom queries with specific field selection

### `bulk <query-file>` — start a bulk operation

```bash
QUERY=$(cat "$1")
shopify_gql "
mutation {
  bulkOperationRunQuery(query: \"\"\"$QUERY\"\"\") {
    bulkOperation { id status }
    userErrors { field message }
  }
}"
echo "Poll status: /shopify gql 'query { currentBulkOperation { id status objectCount url } }'"
```

## Implementation notes

- **GraphQL IDs are GIDs**: `gid://shopify/Product/123456`, not raw numeric.
  REST returns numeric; if mixing, convert with
  `gid://shopify/<Type>/<id>`.
- **Cost-based throttling**: every GraphQL response includes
  `extensions.cost.requestedQueryCost` and `currentlyAvailable`. Skill should
  check before submitting expensive queries.
- **Pagination**: GraphQL uses Relay-style `first`/`after` cursors. For
  >100 items, paginate with `pageInfo.endCursor`.
- **`unstable` version**: never default to it. Bug fixes only land in stable
  versions.
- **Webhooks vs polling**: prefer webhooks for real-time. This skill is for
  ad-hoc reads/writes, not background sync.

## Safety

- **`access_token` is full app permission scope** — leak = full access
  within the granted scopes for that store. Always `chmod 600` the creds
  file. Skill **never** prints token in full — masks as `****<last4>`.
- **Mutating ops** (`update-product`, `update-inventory`, `draft-order
  create`) all go through `ctt_confirm`. Set `require_confirm = true` on
  the prod store profile for an extra layer.
- **`update-product` requires typing the product ID** to confirm — same
  pattern as Heroku app destroy.
- **Destructive ops not in this skill** (intentionally): product delete,
  customer delete, order cancel. Use Shopify admin UI for those — forces
  conscious action.
- **Rate limit awareness**: skill should check `extensions.cost` and back
  off if `currentlyAvailable < requestedQueryCost`. Default behavior is to
  surface rate-limit errors to user, not retry.
- **PII**: customer/order data contains email, phone, address, payment
  status. Treat as **confidential**. Don't paste raw output in public chat.
- **Webhook URLs**: if listed via `webhooks` command, the `callbackUrl` may
  reveal internal infra hostnames. Redact when sharing.
- **Bulk operations** download `.jsonl` files via signed URL. URLs expire
  in 7 days but contain auth tokens — never share publicly.
- Compromise: revoke at Shopify admin → Settings → Apps → your custom app
  → Uninstall. Recreate with new token.

## Token-saving tips

- Use **field selection** in GraphQL — request only what you need.
  `products(first:5){ edges{ node{ id title } } }` costs less than full
  product objects.
- Use **`first: N` with small N** for initial exploration, paginate only if
  needed.
- For one-time bulk reads, use **Bulk Operations** (single async query
  beats N paginated requests cost-wise).
- Avoid `unstable` — schema changes mid-development waste tokens debugging.
