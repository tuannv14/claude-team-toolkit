# /shopify — command bodies

GraphQL queries and mutations for the subcommands listed in [SKILL.md](SKILL.md).
All snippets assume `shopify_gql` from SKILL.md is sourced.

## `shop` — current shop info
```bash
shopify_gql 'query { shop { name email myshopifyDomain currencyCode plan { displayName } } }' | jq '.data.shop'
```

## `products [--limit N] [--query "title:foo"]`
```bash
LIMIT="${LIMIT:-10}"; case "$LIMIT" in ''|*[!0-9]*) LIMIT=10 ;; esac
shopify_gql '
query($f:Int!, $q:String) {
  products(first:$f, query:$q) {
    edges { node { id title handle status totalInventory priceRangeV2 { minVariantPrice { amount currencyCode } } } }
  }
}' "$(jq -n --argjson f "$LIMIT" --arg q "$QUERY" '{f:$f, q:$q}')"
```

## `product <gid>` — full product (id = `gid://shopify/Product/<num>`)
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

## `orders [--status open|closed|any] [--limit N]`
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

## `order <gid>` — full order with line items + fulfillments
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

## `customers [--query] [--limit N]`
```bash
shopify_gql '
query($f:Int!, $q:String) {
  customers(first:$f, query:$q) {
    edges { node { id displayName email phone numberOfOrders amountSpent { amount } } }
  }
}' "$(jq -n --argjson f "$LIMIT" --arg q "$QUERY" '{f:$f, q:$q}')"
```

## `inventory <variant-gid>` — levels per location
```bash
shopify_gql '
query($id:ID!) {
  productVariant(id:$id) {
    id sku title
    inventoryItem { tracked inventoryLevels(first:10) { edges { node { available location { name } } } } }
  }
}' "$(jq -n --arg id "$VARIANT_ID" '{id:$id}')"
```

## `update-product <gid> <field=value>...` — DESTRUCTIVE
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

## `update-inventory <variant-gid> <count> [--location <gid>]` — DESTRUCTIVE
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

## `gql <query-file-or-string> [variables-json]` — raw escape hatch
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
