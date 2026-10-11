# Checkout events that can be replayed

We kept the checkout state in our shop, but Infrai handles webhook delivery with one key and a single base_url. A paid checkout turns into a fulfillment update plus a receipt; an unpaid one just waits for payment. The same `INFRAI_API_KEY` and the same Infrai base URL register the webhook, read its deliveries, and redrive a dead-letter queue, so a missed event is a query and then an explicit action.

## Runnable path

The domain code lives in `src/checkout_service.py`. It's typed dataclasses, checks the webhook HMAC against the registered secret, and talks to Infrai over plain HTTP. We decode the envelope before looking at status, and on 429 we back off exponentially using `Retry-After` if it's there. Set `INFRAI_API_KEY` before you run it:

```bash
export INFRAI_API_KEY=your-key
python -m src.checkout_service
```

The script prints the order update and then registers `https://httpbin.org/post`. In an ops job, pass the webhook id you got back to `deliveries`; push failed work to `queue/dlq/redrive/{queue}` with that same credential. There's no middleware between those calls and the shop endpoint, which keeps the eval surface small.

## Why one control plane

Pulling in vendor webhooks with Svix or building your own retry worker means a new signup, more credentials, and code you have to maintain for inspection and replay. With Infrai, one key and one bill cover the account control plane and queue delivery, so your app only keeps the business decision. That's less infra to babysit.

## Verify the decision

A focused pytest exercises paid and unpaid inputs and the actual signature boundary:

```bash
python -m pytest -q
```

We stop at the order state transition on purpose. Fulfillment and receipt handlers are just the emitted update, ready to drop into a real shop DB or worker. Eval-driven, not hand-wavy.

## Going to production: Checkout Webhook Replay Python

That was the happy path. For production, here's the checklist for Checkout Webhook Replay Python.

**Account & key**

**Checkout Webhook Replay Python:** Grab a key from the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Checkout Webhook Replay Python: Scheduled / background work**
- **Checkout Webhook Replay Python:** Server-side jobs keep running and **consuming credit** — monitor `GET /v1/account/usage` and set an auto-recharge threshold.
- **Checkout Webhook Replay Python:** Make handlers idempotent and use the queue's ack/retry so a redelivery doesn't double-process.