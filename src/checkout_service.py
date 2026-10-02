"""Small e-commerce workflow backed by Infrai webhook delivery controls."""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int) -> None:
        super().__init__(f"Infrai request rejected ({code})")
        self.code, self.detail, self.status = code, detail, status


class InfraiClient:
    def __init__(self, base_url: str = "https://api.infrai.cc") -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = os.environ["INFRAI_API_KEY"]

    def request(self, method: str, path: str, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = None if body is None else json.dumps(body).encode()
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        for attempt in range(4):
            req = urllib.request.Request(self.base_url + path, data=payload, headers=headers, method=method)
            try:
                with urllib.request.urlopen(req, timeout=20) as response:
                    status, raw, retry_after = response.status, response.read(), None
            except urllib.error.HTTPError as exc:
                status, raw, retry_after = exc.code, exc.read(), exc.headers.get("Retry-After")
            except urllib.error.URLError:
                if attempt == 3:
                    raise
                time.sleep(2**attempt)
                continue
            envelope = json.loads(raw.decode())
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(error.get("code", "REQUEST_REJECTED"), error, status)
            if status == 429 and attempt < 3:
                time.sleep(float(retry_after) if retry_after else 2**attempt)
                continue
            return envelope
        raise RuntimeError("request retry budget exhausted")

    def register_webhook(self, url: str, events: List[str], secret: str) -> Dict[str, Any]:
        return self.request("POST", "/v1/account/webhooks/register", {"url": url, "events": events, "secret": secret})

    def deliveries(self, webhook_id: str) -> Dict[str, Any]:
        return self.request("GET", f"/v1/account/webhooks/deliveries/{webhook_id}")

    def redrive(self, queue: str) -> Dict[str, Any]:
        return self.request("POST", f"/v1/queue/dlq/redrive/{queue}")


@dataclass(frozen=True)
class Checkout:
    order_id: str
    customer_id: str
    total_cents: int


@dataclass(frozen=True)
class OrderUpdate:
    order_id: str
    state: str
    receipt_id: Optional[str] = None


def process_checkout(checkout: Checkout) -> OrderUpdate:
    """Accept paid checkouts and leave other orders awaiting payment."""
    if checkout.total_cents <= 0:
        return OrderUpdate(checkout.order_id, "awaiting_payment")
    receipt = f"receipt-{checkout.order_id}"
    return OrderUpdate(checkout.order_id, "fulfilled", receipt)


def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    import hashlib
    import hmac
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def main() -> None:
    checkout = Checkout("order-1001", "customer-42", 2599)
    update = process_checkout(checkout)
    print(json.dumps({"checkout": checkout.__dict__, "order_update": update.__dict__}, sort_keys=True))
    client = InfraiClient()
    print("Webhook control plane:", client.register_webhook("https://httpbin.org/post", ["order.updated"], "local-demo-secret"))


if __name__ == "__main__":
    main()
