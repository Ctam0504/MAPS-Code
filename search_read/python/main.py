from models.currency import Currency
from models.payment_request import PaymentRequest
from strategies.credit_card_strategy import CreditCardStrategy
from services.payment_processor import PaymentProcessor
from exceptions.gateway_exception import GatewayException

def main():
    request = PaymentRequest("REQ_001", 100.0, Currency.USD)
    processor = PaymentProcessor(CreditCardStrategy())

    try:
        processor.execute(request)
    except GatewayException as e:
        print(f"Lỗi: {e.message}")

if __name__ == "__main__":
    main()
