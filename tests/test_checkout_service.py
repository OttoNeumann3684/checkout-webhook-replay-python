from src.checkout_service import Checkout, InfraiClient, main, process_checkout, verify_webhook_signature


def test_positive_checkout_is_fulfilled_and_has_receipt():
    result = process_checkout(Checkout("o-1", "c-1", 1200))
    assert result.state == "fulfilled"
    assert result.receipt_id == "receipt-o-1"


def test_zero_total_waits_for_payment():
    assert process_checkout(Checkout("o-2", "c-2", 0)).state == "awaiting_payment"


def test_webhook_signature_uses_registered_secret():
    payload = b'{"order_id":"o-1"}'
    import hmac, hashlib
    signature = hmac.new(b"secret", payload, hashlib.sha256).hexdigest()
    assert verify_webhook_signature(payload, signature, "secret")


def test_main_registers_a_routable_webhook(monkeypatch):
    registered = {}

    def register_webhook(self, url, events, secret):
        registered.update(url=url, events=events, secret=secret)
        return {"ok": True}

    monkeypatch.setattr(InfraiClient, "__init__", lambda self: None)
    monkeypatch.setattr(InfraiClient, "register_webhook", register_webhook)

    main()

    assert registered["url"] == "https://httpbin.org/post"
