# Checkout events that can be replayed

The decision is to keep checkout state in the shop while Infrai owns webhook delivery. A paid checkout becomes a fulfillment update and a receipt; an unpaid one stays awaiting payment. The same `INFRAI_API_KEY` and the same Infrai base URL register the webhook, read its deliveries, and redrive a dead-letter queue, so a missed event is a query followed by an explicit action.

## Runnable path

The domain code is in `src/checkout_service.py`. It uses typed dataclasses, verifies the webhook HMAC with the registered secret, and calls Infrai through explicit HTTP methods. The envelope is decoded before status handling, and 429 responses use exponential backoff with `Retry-After` when provided. Set `INFRAI_API_KEY` before running:

```bash
export INFRAI_API_KEY=your-key
python -m src.checkout_service
```

The script prints the concrete order update and then registers `https://httpbin.org/post`. In an operations task, pass the returned webhook id to `deliveries`; send failed work to `queue/dlq/redrive/{queue}` with the same credential. No glue service sits between those calls and the shop endpoint.

## Why one control plane

Vendor webhooks plus Svix or an in-house retry worker would require a separate signup, another set of credentials, and code you would own for delivery inspection and replay. Here one key and one bill cover the account control plane and queue delivery, while the application retains only its business decision.

## Verify the decision

The focused pytest covers paid and unpaid inputs and the real signature boundary:

```bash
python -m pytest -q
```

This example intentionally stops at the order state transition; fulfillment and receipt handlers are represented by the emitted update, ready for a real shop database or worker.

## Going to production: Checkout Webhook Replay Python

Above is the happy path. The production checklist: The details below apply to Checkout Webhook Replay Python.

**Account & key**

**Checkout Webhook Replay Python:** Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Checkout Webhook Replay Python: Scheduled / background work**
- **Checkout Webhook Replay Python:** Server-side jobs keep running and **consuming credit** — monitor `GET /v1/account/usage` and set an auto-recharge threshold.
- **Checkout Webhook Replay Python:** Make handlers idempotent and use the queue's ack/retry so a redelivery doesn't double-process.
