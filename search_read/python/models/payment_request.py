from models.currency import Currency

class PaymentRequest:
    def __init__(self, request_id: str, amount: float, currency: Currency):
        self.request_id = request_id
        self.amount = amount
        self.currency = currency
