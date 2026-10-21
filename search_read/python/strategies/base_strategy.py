from abc import ABC, abstractmethod
from models.payment_request import PaymentRequest

class IPaymentStrategy(ABC):
    @abstractmethod
    def pay(self, request: PaymentRequest) -> bool:
        pass
