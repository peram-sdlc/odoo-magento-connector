# SDLC Magento Connector — Real-time / Mapping Setup

This document covers the six features your client requested and how to enable
them after upgrading the module.

```
Magento 2  ──► (REST API + Webhooks) ──►  Odoo 19
                                  ▲
                                  │
                       Webhook → magento.sync.queue → cron worker
                                                       └─► sale.order
                                                           account.move
                                                           magento.product.map
```

## 1. Real-time sync (webhooks)

* Endpoint: `POST /magento/webhook/<instance_id>/<event>`
* Supported events: `order.placed`, `order.created`, `order.updated`,
  `invoice.created`, `creditmemo.created`, `shipment.created`, `stock.updated`,
  `customer.created`, `customer.updated`.
* Authentication: HMAC-SHA256 of the request body using the shared secret on
  the instance, sent in the `X-Magento-Hmac` header.
* Idempotency: `X-Magento-Event-Id` header (or auto-derived from
  entity_id / id / sku); duplicate deliveries are dropped.
* Fallback: events are written to `magento.sync.queue`. The cron
  *Magento Sync Queue Processor* (every 2 min) retries failed jobs with
  exponential backoff (max 5 retries). The pre-existing 10-min order/product
  cron continues to run as a safety net.

### Setup steps

1. Open `Magento → Instances → <your instance> → Real-time / Webhooks`.
2. Tick **Real-time Webhooks**, click **Generate Secret**, save.
3. Copy the secret to your Magento side (custom extension or
   community webhook module like `mageplaza_webhook`).
4. Add a webhook for each event you want, pointing to:
   `https://<odoo-host>/magento/webhook/<instance_id>/<event>`
5. Use payload template `{{ raw }}` (full JSON body).
6. Add HTTP header `X-Magento-Hmac: {{ hmac_sha256(body, secret) }}`.

## 2. Order sync

Already implemented — webhooks now push orders in real-time. The connector
maps customer, products, taxes, shipping, and payment method, and stores the
Magento order id on `sale.order.magento_order_id`.

## 3. Credit memos (refunds)

* On every credit memo event the connector creates an `account.move`
  (out_refund), maps refunded line items 1:1 to `sale.order.line.magento_item_id`
  and posts the refund.
* If the instance has **Auto Restock on Credit Memo** enabled (default),
  it also creates and validates a `stock.return.picking` to reverse the
  shipped quantities.
* Partial and multiple refunds are supported — each Magento credit memo
  becomes its own refund + return picking.

## 4. Tax mapping

* Model: `magento.tax.mapping` (Magento tax class id → Odoo fiscal position
  + default tax).
* Sync from the instance form: **Sync Tax Classes** button.
* Map each class to:
  * **Fiscal Position** — applied to the order.
  * **Default Tax** — applied to order lines when Magento omits line-level tax.
* For Indian GST: create CGST/SGST/IGST taxes in Odoo, group them into a
  fiscal position per state, and map Magento's `taxable goods` /
  `services` classes to the matching position.

## 5. Magento side requirements

The connector uses the Magento 2 native REST API only — no custom Magento
extension is required for sync. **Webhooks** require either:

  a) a community webhook extension (e.g. Mageplaza, Bsscommerce), or
  b) the SDLC sample observer module (`SDLC_OdooSync`, optional) that ships
     with this connector.

Either way, signing must use HMAC-SHA256 with the shared secret.

## 6. Multi-warehouse (MSI)

* Tick **Magento MSI Enabled** on the instance form.
* Click **Sync MSI Sources** — pulls all sources via
  `/rest/V1/inventory/sources`.
* For each source, set the Odoo **Warehouse** and (optionally) mark one as
  the default.
* Stock pushes from Odoo go to `/rest/V1/inventory/source-items` per source.
* Stock pulls from Magento update the Odoo warehouse's quants. The connector
  picks up `source_code` from `stock.updated` webhooks.

## 7. Customer groups & pricing

* Sync from the instance form: **Sync Customer Groups** button.
* For each group, set:
  * **Pricelist** — applied to imported orders and any new sales orders for
    Magento customers in that group.
  * **Fiscal Position** — optional override of the product tax-class fiscal
    position.
* The connector reads `customer_group_id` from the Magento order payload to
  pick the right pricelist.

## Data models

| Model                       | Purpose                                  |
|-----------------------------|------------------------------------------|
| `magento.instance`          | Magento connection + feature toggles     |
| `magento.tax.mapping`       | Tax class ↔ Odoo fiscal position / tax  |
| `magento.source.mapping`    | MSI source ↔ Odoo warehouse             |
| `magento.customer.group`    | Customer group ↔ pricelist              |
| `magento.sync.queue`        | Webhook event queue + retries            |
| `magento.sync.report`       | Per-run sync results (existing)          |

## Error handling & logs

* All webhook + cron errors are written to `magento.sync.queue.last_error`
  with `retry_count` and rescheduled with backoff up to 60 minutes.
* Manual retry: open the queue entry → **Retry** button.
* `_logger.warning` / `_logger.exception` calls flow into the Odoo log.
* Existing `magento.sync.report` continues to record manual & cron runs.

## Performance

* Webhook handler is non-blocking — events are persisted and processed by
  the cron worker so HTTP responses stay under Magento's timeout.
* Queue processes are committed per-job, so a single failure cannot
  rollback the rest of a batch.

## Security

* HMAC-SHA256 verification on every webhook request.
* Constant-time comparison via `hmac.compare_digest`.
* Secrets stored on the instance record only — never logged.
* Controllers are `auth="public"` (Magento can't authenticate as an Odoo
  user) but reject any request without a valid signature.
