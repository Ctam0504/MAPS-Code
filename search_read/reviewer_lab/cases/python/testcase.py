request = PaymentRequest("REQ_001", 100.0, Currency.USD)
processor = PaymentProcessor(PaypalStrategy())
assert processor.execute(request) is True