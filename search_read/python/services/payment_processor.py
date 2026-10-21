from strategies.base_strategy import IPaymentStrategy
from models.payment_request import PaymentRequest

class PaymentProcessor:
    def __init__(self, strategy: IPaymentStrategy):
        self.strategy = strategy

    def set_strategy(self, strategy: IPaymentStrategy) -> None:
        self.strategy = strategy

    def execute(self, request: PaymentRequest) -> bool:
        return False 
