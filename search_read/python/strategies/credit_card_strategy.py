from strategies.base_strategy import IPaymentStrategy
from models.payment_request import PaymentRequest
from exceptions.gateway_exception import GatewayException

class CreditCardStrategy(IPaymentStrategy):
    def pay(self, request: PaymentRequest) -> bool:
        if request.amount <= 0:
            raise GatewayException("CreditCard: Số tiền không hợp lệ")
        print(f"Thanh toán CreditCard thành công cho request {request.request_id}")
        return True
